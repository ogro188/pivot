import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchSignals, fetchLogs, startAsset, stopAsset, fetchHistory, fetchAssets, fetchAssetNtfy, saveAssetNtfy, testAssetNtfy } from '../api'
import { useStore } from '../store'
import ChartHost from '../components/ChartHost'
import SignalCard from '../components/SignalCard'
import SignalCountdown from '../components/SignalCountdown'
import DetectorReadout from '../components/DetectorReadout'

const DEFAULT_PARAMS = {
  confianza_minima: 65,
  reward_ratio_min: 1.5,
  usar_kill_zones: false,
  usar_trend_d1: false,
  risk_por_operacion: 1.0,
  slippage_pips: 1.0,
  comision_lote: 0.5,
}

function normalizarDetectores(detectores?: string[]): string[] {
  if (!detectores || !Array.isArray(detectores)) return []
  const raices = ['D0', 'D1', 'D2', 'D3', 'D4', 'D5']
  const set = new Set<string>()
  detectores.forEach((d) => {
    const m =/^D[0-5]/.exec(String(d))
    if (m && raices.includes(m[0])) set.add(m[0])
  })
  return raices.filter((r) => set.has(r))
}

export default function ActivoPage() {
  const { simbolo } = useParams<{ simbolo: string }>()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<'signals' | 'consola' | 'strategies'>('signals')
  const [tf, setTf] = useState('M15')
  const [multiTf, setMultiTf] = useState(false)
  const candles = useStore((s) => s.candles[`${simbolo}:${tf}`] || [])
  const candlesH1 = useStore((s) => s.candles[`${simbolo}:H1`] || [])
  const candlesH4 = useStore((s) => s.candles[`${simbolo}:H4`] || [])
  const setCandles = useStore((s) => s.setCandles)
  const globalSignals = useStore((s) => s.globalSignals)
  const assetConfig = useStore((s) => s.getAssetConfig(simbolo || ''))
  const setAssetConfig = useStore((s) => s.setAssetConfig)

  const [ntfyTopic, setNtfyTopic] = useState('')
  const [ntfyServer, setNtfyServer] = useState('https://ntfy.sh')
  const [ntfyStatus, setNtfyStatus] = useState<{ ok: boolean; msg: string } | null>(null)
  const [ntfyTesting, setNtfyTesting] = useState(false)

  useEffect(() => {
    if (!simbolo) return
    fetchAssetNtfy(simbolo).then((cfg) => {
      setNtfyTopic(cfg.topic || '')
      setNtfyServer(cfg.server || 'https://ntfy.sh')
    }).catch(() => {})
  }, [simbolo])

  const handleSaveNtfy = async () => {
    try {
      await saveAssetNtfy(simbolo!, ntfyTopic, ntfyServer)
      setNtfyStatus({ ok: true, msg: 'Configuración guardada' })
    } catch {
      setNtfyStatus({ ok: false, msg: 'Error al guardar' })
    }
  }

  const handleTestNtfy = async () => {
    setNtfyTesting(true)
    setNtfyStatus(null)
    try {
      const res = await testAssetNtfy(simbolo!)
      setNtfyStatus({ ok: !!res.ok, msg: res.detail || (res.ok ? 'Notificación enviada' : 'Falló') })
    } catch {
      setNtfyStatus({ ok: false, msg: 'Error de conexión' })
    } finally {
      setNtfyTesting(false)
    }
  }

  const { data: assets } = useQuery({ queryKey: ['assets'], queryFn: fetchAssets, refetchInterval: 5000 })
  const running = assets?.find((a: any) => a.simbolo === simbolo)?.running ?? false
  const asset = assets?.find((a: any) => a.simbolo === simbolo)
  const derivConnected = useStore((s) => s.derivConnected)

  const { data: signals, refetch: refetchSignals } = useQuery({
    queryKey: ['signals', simbolo],
    queryFn: () => fetchSignals(simbolo!),
    refetchInterval: 5000,
    enabled: !!simbolo
  })
  const { data: logs } = useQuery({
    queryKey: ['logs', simbolo],
    queryFn: () => fetchLogs(simbolo!),
    refetchInterval: 5000,
    enabled: !!simbolo
  })

  // Cargar velas para timeframe actual
  useEffect(() => {
    if (!simbolo) return
    fetchHistory(simbolo, tf, 200).then((data) => {
      setCandles(simbolo, tf, data)
    }).catch(() => {
      setCandles(simbolo, tf, [])
    })
    const iv = setInterval(() => {
      fetchHistory(simbolo, tf, 200).then((data) => {
        setCandles(simbolo, tf, data)
      }).catch(() => {})
    }, 5000)
    return () => clearInterval(iv)
  }, [simbolo, tf, setCandles])

  // Cargar H1 y H4 cuando se activa multi-timeframe
  useEffect(() => {
    if (!multiTf || !simbolo) return
    const load = async () => {
      try {
        const [h1, h4] = await Promise.all([
          fetchHistory(simbolo, 'H1', 200),
          fetchHistory(simbolo, 'H4', 200),
        ])
        setCandles(simbolo, 'H1', h1)
        setCandles(simbolo, 'H4', h4)
      } catch {}
    }
    load()
    const iv = setInterval(load, 30000)
    return () => clearInterval(iv)
  }, [multiTf, simbolo, setCandles])

  const handleStart = async () => {
    try {
      await startAsset(simbolo!)
      queryClient.invalidateQueries({ queryKey: ['assets'] })
      refetchSignals()
    } catch {
      // endpoint no disponible o sin datos
    }
  }

  const handleStop = async () => {
    try {
      await stopAsset(simbolo!)
      queryClient.invalidateQueries({ queryKey: ['assets'] })
    } catch {
      // endpoint no disponible
    }
  }

  // Filtrar señales para el timeframe actual
  const currentSignals = globalSignals.filter(
    (s) => s.asset === simbolo && (s.timeframe || 'M15') === tf
  )

  // Señal más reciente del activo (sin filtro de TF) para el readout de detectores
  const ultimaSenal = globalSignals.find((s) => s.asset === simbolo && s.detectores && s.detectores.length > 0)
  const detectoresActivos = normalizarDetectores(ultimaSenal?.detectores)

  // Config por activo
  const params = { ...DEFAULT_PARAMS, ...assetConfig }
  const handleParamChange = (k: string, v: any) => {
    setAssetConfig(simbolo || '', { ...params, [k]: v })
  }
  const handleResetParams = () => {
    setAssetConfig(simbolo || '', {})
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <div className="flex items-center gap-3">
          <h1 className="font-mono font-semibold text-base text-text-primary">{simbolo}</h1>
          {asset?.fuente === 'deriv' && (
            <div className={`flex items-center gap-1.5 font-condensed text-[10px] tracking-widest uppercase ${derivConnected ? 'text-brand-cyan' : 'text-text-muted'}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${derivConnected ? 'bg-brand-cyan animate-pulse-dot' : 'bg-base-line'}`} />
              Deriv {derivConnected ? 'ON' : 'OFF'}
            </div>
          )}
        </div>
        <div className="flex gap-2">
          <button onClick={handleStart} className={`px-3 py-1 font-condensed text-[11px] tracking-widest uppercase transition-colors ${running ? 'bg-base-panel2 border border-base-line text-text-muted cursor-default' : 'border border-brand-cyan/50 text-brand-cyan hover:bg-brand-cyan/10'}`}>
            {running ? 'Live' : 'Start'}
          </button>
          <button onClick={handleStop} disabled={!running} className={`px-3 py-1 font-condensed text-[11px] tracking-widest uppercase transition-colors ${running ? 'border border-base-line text-text-secondary hover:text-text-primary' : 'bg-base-panel2 border border-base-line text-text-muted cursor-default'}`}>
            Stop
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-3">
        {['M15', 'H1', 'H4', 'D1'].map((t) => (
          <button key={t} onClick={() => { setMultiTf(false); setTf(t) }} className={`font-condensed text-[11px] px-2 py-1 tracking-widest transition-colors ${tf === t && !multiTf ? 'border border-brand-cyan bg-brand-cyan/10 text-brand-cyan' : 'border border-base-line bg-base-panel text-text-secondary hover:text-text-primary'}`}>
            {t}
          </button>
        ))}
        <label className="flex items-center gap-1 font-condensed text-[11px] text-text-secondary uppercase tracking-widest">
          <input type="checkbox" checked={multiTf} onChange={(e) => setMultiTf(e.target.checked)} className="w-4 h-4 accent-brand-cyan" />
          Multi-TF
        </label>
      </div>

      <div className="flex flex-col xl:flex-row xl:gap-3">
        {/* Columna principal: charts + tabs */}
        <div className="flex-1 min-w-0">
          {/* Charts */}
          {!multiTf ? (
            <ChartHost candles={candles} signals={currentSignals} height={400} asset={asset} id={`${simbolo}:${tf}`} />
          ) : (
            <div className="space-y-3">
              <ChartHost candles={candles} signals={globalSignals.filter((s) => s.asset === simbolo && (s.timeframe || 'M15') === 'M15')} height={250} asset={asset} id={`${simbolo}:M15`} />
              <ChartHost candles={candlesH1} signals={globalSignals.filter((s) => s.asset === simbolo && (s.timeframe || 'M15') === 'H1')} height={250} asset={asset} id={`${simbolo}:H1`} />
              <ChartHost candles={candlesH4} signals={globalSignals.filter((s) => s.asset === simbolo && (s.timeframe || 'M15') === 'H4')} height={250} asset={asset} id={`${simbolo}:H4`} />
            </div>
          )}

          <div className="flex gap-2 border-b border-base-line pb-2 mt-3">
            {(['signals', 'consola', 'strategies'] as const).map((t) => (
              <button key={t} onClick={() => setTab(t)} className={`font-condensed text-[11px] tracking-widest uppercase px-2 py-1 ${tab === t ? 'text-brand-cyan border-b-2 border-brand-cyan' : 'text-text-secondary hover:text-text-primary'}`}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
          {tab === 'signals' && (
            <div className="space-y-2 mt-2">
              {signals?.map((s: any) => <SignalCard key={`${s.id}-${s.ts}`} signal={s} />)}
              {(!signals || signals.length === 0) && (
                <div className="text-text-muted text-sm">No hay señales aún. Inicia el activo para generar el replay.</div>
              )}
            </div>
          )}
          {tab === 'consola' && (
            <div className="bg-base-panel border border-base-line p-3 font-mono text-xs space-y-1 max-h-96 overflow-y-auto mt-2">
              {logs?.map((l: any, i: number) => (
                <div key={i} className={`${l.level === 'ERROR' ? 'font-bold text-text-primary' : l.level === 'WARN' ? 'text-text-primary' : 'text-text-secondary'}`}>
                  <span className="text-text-muted">{l.t}</span> <span className="font-bold text-text-primary">{l.cat}</span> {l.msg}
                </div>
              ))}
              {(!logs || logs.length === 0) && (
                <div className="text-text-muted">Sin logs.</div>
              )}
            </div>
          )}
          {tab === 'strategies' && (
            <div className="mt-2 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-1">Confianza mínima</label>
                  <input type="number" min="0" max="100" step="1" className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-sm text-text-primary tabular" value={params.confianza_minima} onChange={(e) => handleParamChange('confianza_minima', parseInt(e.target.value))} />
                </div>
                <div>
                  <label className="block font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-1">Reward ratio mínimo</label>
                  <input type="number" min="0.5" max="5" step="0.1" className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-sm text-text-primary tabular" value={params.reward_ratio_min} onChange={(e) => handleParamChange('reward_ratio_min', parseFloat(e.target.value))} />
                </div>
                <div>
                  <label className="block font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-1">Risk % por operación</label>
                  <input type="number" min="0.1" max="10" step="0.1" className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-sm text-text-primary tabular" value={params.risk_por_operacion} onChange={(e) => handleParamChange('risk_por_operacion', parseFloat(e.target.value))} />
                </div>
                <div>
                  <label className="block font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-1">Slippage (pips)</label>
                  <input type="number" min="0" max="10" step="0.1" className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-sm text-text-primary tabular" value={params.slippage_pips} onChange={(e) => handleParamChange('slippage_pips', parseFloat(e.target.value))} />
                </div>
                <div>
                  <label className="block font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-1">Comisión por lote</label>
                  <input type="number" min="0" max="10" step="0.1" className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-sm text-text-primary tabular" value={params.comision_lote} onChange={(e) => handleParamChange('comision_lote', parseFloat(e.target.value))} />
                </div>
                <div className="flex items-end gap-3">
                  <label className="flex items-center gap-1 font-condensed text-[11px] tracking-widest text-text-secondary uppercase">
                    <input type="checkbox" checked={params.usar_kill_zones} onChange={(e) => handleParamChange('usar_kill_zones', e.target.checked)} className="w-4 h-4 accent-brand-cyan" />
                    Usar Kill Zones
                  </label>
                  <label className="flex items-center gap-1 font-condensed text-[11px] tracking-widest text-text-secondary uppercase">
                    <input type="checkbox" checked={params.usar_trend_d1} onChange={(e) => handleParamChange('usar_trend_d1', e.target.checked)} className="w-4 h-4 accent-brand-cyan" />
                    Usar Trend D1
                  </label>
                </div>
                <button onClick={handleResetParams} className="bg-base-panel2 hover:bg-base-line text-text-secondary px-3 py-1 font-condensed text-[11px] tracking-widest uppercase transition-colors">
                  Restablecer defaults
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Rail derecho */}
        <div className="xl:w-64 shrink-0 mt-4 xl:mt-0 space-y-3">
          <DetectorReadout activos={detectoresActivos} />
          <div className="panel p-2.5 space-y-1.5">
            <div className="font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-2">Sesión</div>
            <div className="flex justify-between items-center">
              <span className="font-condensed text-[11px] text-text-secondary uppercase tracking-widest">Sesión</span>
              <span className="font-mono text-[11px] text-text-primary tabular">{asset?.session || '—'}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="font-condensed text-[11px] text-text-secondary uppercase tracking-widest">Kill Zone</span>
              <span className="font-mono text-[11px] text-text-primary tabular">{asset?.kill_zone || '—'}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="font-condensed text-[11px] text-text-secondary uppercase tracking-widest">Detectores DF</span>
              <span className="font-mono text-[11px] text-brand-cyan tabular">{detectoresActivos.length} D</span>
            </div>
          </div>
          <div className="panel p-2.5 space-y-1.5">
            <div className="font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-2">Notificaciones ntfy</div>
            <div>
              <label className="block font-condensed text-[10px] tracking-widest text-text-muted uppercase mb-1">Topic</label>
              <input className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-xs text-text-primary" value={ntfyTopic} onChange={(e) => setNtfyTopic(e.target.value)} placeholder="mi-topic-secreto" />
            </div>
            <div>
              <label className="block font-condensed text-[10px] tracking-widest text-text-muted uppercase mb-1">Server</label>
              <input className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-xs text-text-primary" value={ntfyServer} onChange={(e) => setNtfyServer(e.target.value)} placeholder="https://ntfy.sh" />
            </div>
            <div className="flex gap-2 pt-1">
              <button onClick={handleSaveNtfy} className="flex-1 bg-base-panel2 hover:bg-base-line text-text-secondary px-2 py-1 font-condensed text-[10px] tracking-widest uppercase transition-colors">
                Guardar
              </button>
              <button onClick={handleTestNtfy} disabled={ntfyTesting || !ntfyTopic} className={`flex-1 px-2 py-1 font-condensed text-[10px] tracking-widest uppercase transition-colors ${ntfyTesting || !ntfyTopic ? 'bg-base-panel2 border border-base-line text-text-muted cursor-default' : 'border border-brand-cyan/50 text-brand-cyan hover:bg-brand-cyan/10'}`}>
                {ntfyTesting ? 'Probando…' : 'Test'}
              </button>
            </div>
            {ntfyStatus && (
              <div className={`text-[10px] font-condensed tracking-wide ${ntfyStatus.ok ? 'text-emerald-400' : 'text-red-400'}`}>
                {ntfyStatus.msg}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}