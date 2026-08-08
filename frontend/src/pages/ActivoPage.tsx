import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchSignals, fetchLogs, startAsset, stopAsset, fetchHistory, fetchAssets } from '../api'
import { useStore } from '../store'
import ChartHost from '../components/ChartHost'
import SignalCard from '../components/SignalCard'
import SignalCountdown from '../components/SignalCountdown'

const DEFAULT_PARAMS = {
  confianza_minima: 65,
  reward_ratio_min: 1.5,
  usar_kill_zones: false,
  usar_trend_d1: false,
  risk_por_operacion: 1.0,
  slippage_pips: 1.0,
  comision_lote: 0.5,
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

  const { data: assets } = useQuery({ queryKey: ['assets'], queryFn: fetchAssets, refetchInterval: 5000 })
  const running = assets?.find((a: any) => a.simbolo === simbolo)?.running ?? false

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

  // Config por activo
  const params = { ...DEFAULT_PARAMS, ...assetConfig }
  const handleParamChange = (k: string, v: any) => {
    setAssetConfig(simbolo || '', { ...params, [k]: v })
  }
  const handleResetParams = () => {
    setAssetConfig(simbolo || '', {})
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">{simbolo}</h1>
        <div className="flex gap-2">
          <button onClick={handleStart} className={`px-3 py-1 rounded text-sm ${running ? 'bg-gray-600 text-gray-300 cursor-default' : 'bg-green-600 hover:bg-green-700 text-white'}`}>
            {running ? 'Live' : 'Start'}
          </button>
          <button onClick={handleStop} disabled={!running} className={`px-3 py-1 rounded text-sm ${running ? 'bg-red-600 hover:bg-red-700 text-white' : 'bg-gray-700 text-gray-500 cursor-default'}`}>
            Stop
          </button>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {['M15', 'H1', 'H4', 'D1'].map((t) => (
          <button key={t} onClick={() => { setMultiTf(false); setTf(t) }} className={`text-xs px-2 py-1 rounded ${tf === t && !multiTf ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'}`}>
            {t}
          </button>
        ))}
        <label className="flex items-center gap-1 text-sm text-gray-300">
          <input type="checkbox" checked={multiTf} onChange={(e) => setMultiTf(e.target.checked)} className="w-4 h-4 accent-blue-600" />
          Multi-TF
        </label>
      </div>

      {/* Charts */}
      {!multiTf ? (
        <ChartHost candles={candles} signals={currentSignals} height={400} />
      ) : (
        <div className="space-y-4">
          <ChartHost candles={candles} signals={globalSignals.filter((s) => s.asset === simbolo && (s.timeframe || 'M15') === 'M15')} height={250} />
          <ChartHost candles={candlesH1} signals={globalSignals.filter((s) => s.asset === simbolo && (s.timeframe || 'M15') === 'H1')} height={250} />
          <ChartHost candles={candlesH4} signals={globalSignals.filter((s) => s.asset === simbolo && (s.timeframe || 'M15') === 'H4')} height={250} />
        </div>
      )}

      <div className="flex gap-2 border-b border-gray-700 pb-2">
        {(['signals', 'consola', 'strategies'] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`px-3 py-1 rounded text-sm ${tab === t ? 'bg-gray-700 text-white' : 'text-gray-400'}`}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      {tab === 'signals' && (
        <div className="space-y-2">
          {signals?.map((s: any) => <SignalCard key={`${s.id}-${s.ts}`} signal={s} />)}
          {(!signals || signals.length === 0) && (
            <div className="text-gray-500 text-sm">No hay señales aún. Inicia el activo para generar el replay.</div>
          )}
        </div>
      )}
      {tab === 'consola' && (
        <div className="bg-gray-800 rounded-lg p-3 font-mono text-xs space-y-1 max-h-96 overflow-y-auto">
          {logs?.map((l: any, i: number) => (
            <div key={i} className={`${l.level === 'ERROR' ? 'text-red-400' : l.level === 'WARN' ? 'text-yellow-400' : 'text-gray-300'}`}>
              <span className="text-gray-500">{l.t}</span> <span className="font-bold">{l.cat}</span> {l.msg}
            </div>
          ))}
          {(!logs || logs.length === 0) && (
            <div className="text-gray-500">Sin logs.</div>
          )}
        </div>
      )}
      {tab === 'strategies' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Confianza mínima</label>
              <input type="number" min="0" max="100" step="1" className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm" value={params.confianza_minima} onChange={(e) => handleParamChange('confianza_minima', parseInt(e.target.value))} />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Reward ratio mínimo</label>
              <input type="number" min="0.5" max="5" step="0.1" className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm" value={params.reward_ratio_min} onChange={(e) => handleParamChange('reward_ratio_min', parseFloat(e.target.value))} />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Risk % por operación</label>
              <input type="number" min="0.1" max="10" step="0.1" className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm" value={params.risk_por_operacion} onChange={(e) => handleParamChange('risk_por_operacion', parseFloat(e.target.value))} />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Slippage (pips)</label>
              <input type="number" min="0" max="10" step="0.1" className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm" value={params.slippage_pips} onChange={(e) => handleParamChange('slippage_pips', parseFloat(e.target.value))} />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Comisión por lote</label>
              <input type="number" min="0" max="10" step="0.1" className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm" value={params.comision_lote} onChange={(e) => handleParamChange('comision_lote', parseFloat(e.target.value))} />
            </div>
            <div className="flex items-end gap-2">
              <label className="flex items-center gap-1 text-sm">
                <input type="checkbox" checked={params.usar_kill_zones} onChange={(e) => handleParamChange('usar_kill_zones', e.target.checked)} className="w-4 h-4 accent-blue-600" />
                Usar Kill Zones
              </label>
              <label className="flex items-center gap-1 text-sm">
                <input type="checkbox" checked={params.usar_trend_d1} onChange={(e) => handleParamChange('usar_trend_d1', e.target.checked)} className="w-4 h-4 accent-blue-600" />
                Usar Trend D1
              </label>
            </div>
            <button onClick={handleResetParams} className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded text-sm">
              Restablecer defaults
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
