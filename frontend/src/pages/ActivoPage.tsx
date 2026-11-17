import { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchSignals, fetchLogs, startAsset, stopAsset, fetchHistory, fetchAssets } from '../api'
import { useStore } from '../store'
import ChartHost, { type VisibleRange } from '../components/ChartHost'
import SignalCard from '../components/SignalCard'
import DetectorReadout from '../components/DetectorReadout'
import AssetNtfyForm from '../components/AssetNtfyForm'
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  FieldLabel,
  PageHeader,
  Panel,
  SkeletonChart,
  useToast,
} from '../components/ui'
import { describeError } from '../utils/errors'
import { normalizarDetectores } from '../utils/signals'

const DEFAULT_PARAMS = {
  confianza_minima: 65,
  reward_ratio_min: 1.5,
  usar_kill_zones: false,
  usar_trend_d1: false,
  risk_por_operacion: 1.0,
  slippage_pips: 1.0,
  comision_lote: 0.5,
}

const TIMEFRAMES = ['M15', 'H1', 'H4', 'D1'] as const

type TabId = 'signals' | 'consola' | 'strategies'

const TABS: { id: TabId; label: string }[] = [
  { id: 'signals', label: 'Señales' },
  { id: 'consola', label: 'Consola' },
  { id: 'strategies', label: 'Parámetros' },
]

export default function ActivoPage() {
  const { simbolo } = useParams<{ simbolo: string }>()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [tab, setTab] = useState<TabId>('signals')
  const [tf, setTf] = useState('M15')
  const [multiTf, setMultiTf] = useState(false)
  const [sharedRange, setSharedRange] = useState<VisibleRange | null>(null)
  const [historyError, setHistoryError] = useState<unknown>(null)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [busy, setBusy] = useState(false)

  const onRangeChange = useCallback((range: VisibleRange) => setSharedRange(range), [])
  const candles = useStore((s) => s.candles[`${simbolo}:${tf}`] || [])
  const candlesH1 = useStore((s) => s.candles[`${simbolo}:H1`] || [])
  const candlesH4 = useStore((s) => s.candles[`${simbolo}:H4`] || [])
  const setCandles = useStore((s) => s.setCandles)
  const globalSignals = useStore((s) => s.globalSignals)
  const assetConfig = useStore((s) => s.getAssetConfig(simbolo || ''))
  const setAssetConfig = useStore((s) => s.setAssetConfig)

  const { data: assets, isLoading: assetsLoading, refetch: refetchAssets } = useQuery({
    queryKey: ['assets'],
    queryFn: fetchAssets,
    refetchInterval: 5000,
  })
  const asset = assets?.find((a: any) => a.simbolo === simbolo)
  const running = asset?.running ?? false
  const derivConnected = useStore((s) => s.derivConnected)

  const {
    data: signals,
    isLoading: signalsLoading,
    error: signalsError,
    refetch: refetchSignals,
  } = useQuery({
    queryKey: ['signals', simbolo],
    queryFn: () => fetchSignals(simbolo!),
    refetchInterval: 5000,
    enabled: !!simbolo,
  })
  const {
    data: logs,
    isLoading: logsLoading,
    error: logsError,
    refetch: refetchLogs,
  } = useQuery({
    queryKey: ['logs', simbolo],
    queryFn: () => fetchLogs(simbolo!),
    refetchInterval: 5000,
    enabled: !!simbolo,
  })

  useEffect(() => {
    if (!simbolo) return
    let cancel = false
    const load = () =>
      fetchHistory(simbolo, tf, 200)
        .then((data) => {
          if (cancel) return
          setCandles(simbolo, tf, data)
          setHistoryError(null)
          setHistoryLoaded(true)
        })
        .catch((err) => {
          if (cancel) return
          setHistoryError(err)
          setHistoryLoaded(true)
        })
    load()
    const iv = setInterval(load, 5000)
    return () => {
      cancel = true
      clearInterval(iv)
    }
  }, [simbolo, tf, setCandles])

  useEffect(() => {
    if (!multiTf || !simbolo) return
    let cancel = false
    const load = async () => {
      try {
        const [h1, h4] = await Promise.all([
          fetchHistory(simbolo, 'H1', 200),
          fetchHistory(simbolo, 'H4', 200),
        ])
        if (cancel) return
        setCandles(simbolo, 'H1', h1)
        setCandles(simbolo, 'H4', h4)
      } catch (err) {
        if (!cancel) setHistoryError(err)
      }
    }
    load()
    const iv = setInterval(load, 30000)
    return () => {
      cancel = true
      clearInterval(iv)
    }
  }, [multiTf, simbolo, setCandles])

  const params = { ...DEFAULT_PARAMS, ...assetConfig }

  const handleStart = async () => {
    setBusy(true)
    try {
      await startAsset(simbolo!, params)
      queryClient.invalidateQueries({ queryKey: ['assets'] })
      refetchSignals()
      toast.success(`${simbolo} iniciado. El runtime está generando señales.`, 'Runtime activo')
    } catch (err) {
      toast.error(describeError(err), 'No se pudo iniciar')
    } finally {
      setBusy(false)
    }
  }

  const handleStop = async () => {
    setBusy(true)
    try {
      await stopAsset(simbolo!)
      queryClient.invalidateQueries({ queryKey: ['assets'] })
      toast.info(`${simbolo} detenido.`, 'Runtime detenido')
    } catch (err) {
      toast.error(describeError(err), 'No se pudo detener')
    } finally {
      setBusy(false)
    }
  }

  const currentSignals = useMemo(
    () => globalSignals.filter((s) => s.asset === simbolo && (s.timeframe || 'M15') === tf),
    [globalSignals, simbolo, tf]
  )
  const senialesM15 = useMemo(
    () => globalSignals.filter((s) => s.asset === simbolo && (s.timeframe || 'M15') === 'M15'),
    [globalSignals, simbolo]
  )
  const senialesH1 = useMemo(
    () => globalSignals.filter((s) => s.asset === simbolo && (s.timeframe || 'M15') === 'H1'),
    [globalSignals, simbolo]
  )
  const senialesH4 = useMemo(
    () => globalSignals.filter((s) => s.asset === simbolo && (s.timeframe || 'M15') === 'H4'),
    [globalSignals, simbolo]
  )
  const ultimaSenal = globalSignals.find(
    (s) => s.asset === simbolo && s.detectores && s.detectores.length > 0
  )
  const detectoresActivos = normalizarDetectores(ultimaSenal?.detectores)

  const handleParamChange = (k: string, v: unknown) => {
    setAssetConfig(simbolo || '', { ...params, [k]: v })
  }
  const handleResetParams = () => {
    setAssetConfig(simbolo || '', {})
    toast.info('Parámetros restaurados a los valores por defecto.')
  }

  const chartLoading = !historyLoaded && !historyError
  const chartHeight = multiTf ? 250 : 400

  const chartArea = chartLoading ? (
    <SkeletonChart height={chartHeight} />
  ) : historyError && candles.length === 0 ? (
    <ErrorState
      title="No se pudieron cargar las velas"
      message={historyError}
      onRetry={() => refetchAssets()}
    />
  ) : !multiTf ? (
    <ChartHost
      candles={candles}
      signals={currentSignals}
      height={chartHeight}
      asset={asset}
      id={`${simbolo}:${tf}`}
    />
  ) : (
    <div className="space-y-3">
      <ChartHost
        candles={candles}
        signals={senialesM15}
        height={chartHeight}
        asset={asset}
        id={`${simbolo}:M15`}
        syncGroup="multi-tf"
        visibleRange={sharedRange}
        onVisibleRangeChange={onRangeChange}
      />
      <ChartHost
        candles={candlesH1}
        signals={senialesH1}
        height={chartHeight}
        asset={asset}
        id={`${simbolo}:H1`}
        toolbar={false}
        syncGroup="multi-tf"
        visibleRange={sharedRange}
        onVisibleRangeChange={onRangeChange}
      />
      <ChartHost
        candles={candlesH4}
        signals={senialesH4}
        height={chartHeight}
        asset={asset}
        id={`${simbolo}:H4`}
        toolbar={false}
        syncGroup="multi-tf"
        visibleRange={sharedRange}
        onVisibleRangeChange={onRangeChange}
      />
    </div>
  )

  return (
    <div>
      <PageHeader
        title={simbolo || '—'}
        eyebrow="Activo"
        description={asset?.nombre}
        actions={
          <>
            {asset?.fuente === 'deriv' && (
              <Badge tone={derivConnected ? 'brand' : 'muted'}>
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    derivConnected ? 'bg-brand-cyan animate-pulse-dot' : 'bg-text-muted'
                  }`}
                />
                Deriv {derivConnected ? 'ON' : 'OFF'}
              </Badge>
            )}
            <Button
              variant="primary"
              icon="play"
              onClick={handleStart}
              disabled={running || busy || !asset}
              loading={busy && !running}
              title={running ? 'El runtime ya está corriendo' : 'Iniciar runtime'}
            >
              Iniciar
            </Button>
            <Button
              variant="secondary"
              icon="stop"
              onClick={handleStop}
              disabled={!running || busy}
              loading={busy && running}
            >
              Detener
            </Button>
          </>
        }
      />

      <div className="flex flex-wrap items-center gap-2 mb-3">
        <div role="group" aria-label="Timeframe" className="flex flex-wrap gap-1">
          {TIMEFRAMES.map((t) => (
            <button
              key={t}
              type="button"
              aria-pressed={tf === t && !multiTf}
              onClick={() => {
                setMultiTf(false)
                setTf(t)
              }}
              className={`font-condensed text-[11px] font-semibold tracking-[0.12em] px-2.5 py-1 border transition-colors ${
                tf === t && !multiTf
                  ? 'border-brand-cyan bg-brand-cyan/10 text-brand-cyan'
                  : 'border-base-edge bg-base-panel text-text-secondary hover:text-text-primary'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        <label
          htmlFor="multi-tf"
          className="flex items-center gap-1.5 font-condensed text-[11px] tracking-[0.12em] uppercase text-text-secondary ml-1"
        >
          <input
            id="multi-tf"
            type="checkbox"
            checked={multiTf}
            onChange={(e) => setMultiTf(e.target.checked)}
            className="w-3.5 h-3.5 accent-brand-cyan"
          />
          Multi-TF
        </label>
        {assetsLoading && (
          <span className="font-condensed text-[10px] uppercase tracking-widest text-text-muted">
            sincronizando…
          </span>
        )}
      </div>

      <div className="flex flex-col xl:flex-row xl:gap-3">
        <div className="flex-1 min-w-0">
          {chartArea}

          <div
            role="tablist"
            aria-label="Paneles del activo"
            className="flex gap-1 border-b border-base-line mt-4"
          >
            {TABS.map((t) => (
              <button
                key={t.id}
                id={`tab-${t.id}`}
                role="tab"
                type="button"
                aria-selected={tab === t.id}
                aria-controls="panel-activo"
                tabIndex={tab === t.id ? 0 : -1}
                onClick={() => setTab(t.id)}
                onKeyDown={(e) => {
                  const idx = TABS.findIndex((x) => x.id === tab)
                  if (e.key === 'ArrowRight') setTab(TABS[(idx + 1) % TABS.length].id)
                  else if (e.key === 'ArrowLeft') setTab(TABS[(idx - 1 + TABS.length) % TABS.length].id)
                  else return
                  e.preventDefault()
                }}
                className={`font-condensed text-[11px] font-semibold tracking-[0.12em] uppercase px-3 py-2 border-b-2 -mb-px transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand-cyan ${
                  tab === t.id
                    ? 'border-brand-cyan text-brand-cyan'
                    : 'border-transparent text-text-secondary hover:text-text-primary'
                }`}
              >
                {t.label}
                {t.id === 'signals' && signals && signals.length > 0 && (
                  <span className="ml-1.5 tabular text-text-muted">({signals.length})</span>
                )}
                {t.id === 'consola' && logs && logs.length > 0 && (
                  <span className="ml-1.5 tabular text-text-muted">({logs.length})</span>
                )}
              </button>
            ))}
          </div>

          <div
            role="tabpanel"
            id="panel-activo"
            aria-labelledby={`tab-${tab}`}
            tabIndex={0}
            className="mt-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-cyan"
          >
            {tab === 'signals' && (
              <div className="space-y-2">
                {signalsLoading && <p className="text-text-muted text-xs">Cargando señales…</p>}
                {signalsError && (
                  <ErrorState
                    title="No se pudieron cargar las señales"
                    message={signalsError}
                    onRetry={() => refetchSignals()}
                    compact
                  />
                )}
                {signals &&
                  signals.length > 0 &&
                  signals.map((s: any) => <SignalCard key={`${s.id}-${s.ts}`} signal={s} />)}
                {signals && signals.length === 0 && !signalsLoading && (
                  <EmptyState
                    icon="activity"
                    title="Sin señales todavía"
                    description="Inicia el runtime para generar el replay y ver las señales acá."
                    compact
                  />
                )}
              </div>
            )}

            {tab === 'consola' && (
              <div
                role="log"
                aria-live="polite"
                aria-label="Consola del activo"
                className="bg-base-panel border border-base-line p-3 font-mono text-xs space-y-1 max-h-96 overflow-y-auto"
              >
                {logsLoading && <p className="text-text-muted">Cargando consola…</p>}
                {logsError && (
                  <ErrorState
                    title="No se pudo cargar la consola"
                    message={logsError}
                    onRetry={() => refetchLogs()}
                    compact
                  />
                )}
                {logs?.map((l: any, i: number) => (
                  <div
                    key={i}
                    className={
                      l.level === 'ERROR'
                        ? 'text-state-error'
                        : l.level === 'WARN'
                          ? 'text-state-warn'
                          : 'text-text-secondary'
                    }
                  >
                    <span className="text-text-muted">{l.t}</span>{' '}
                    <span className="font-semibold text-text-primary">{l.cat}</span> {l.msg}
                  </div>
                ))}
                {logs && logs.length === 0 && !logsLoading && !logsError && (
                  <EmptyState icon="database" title="Sin mensajes" description="La consola del activo aún no registró nada." compact />
                )}
              </div>
            )}

            {tab === 'strategies' && (
              <Panel title="Parámetros de la estrategia" subtitle="Se aplican al iniciar el runtime">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <FieldLabel htmlFor="strat-confianza_minima" hint="0–100">
                      Confianza mínima
                    </FieldLabel>
                    <input
                      id="strat-confianza_minima"
                      type="number"
                      min={0}
                      max={100}
                      step={1}
                      className="w-full bg-base-panel2 border border-base-edge px-2 py-1.5 text-sm text-text-primary tabular"
                      value={params.confianza_minima}
                      onChange={(e) => handleParamChange('confianza_minima', parseInt(e.target.value))}
                    />
                  </div>
                  <div>
                    <FieldLabel htmlFor="strat-reward_ratio_min" hint="0.5–5">
                      Reward ratio mínimo
                    </FieldLabel>
                    <input
                      id="strat-reward_ratio_min"
                      type="number"
                      min={0.5}
                      max={5}
                      step={0.1}
                      className="w-full bg-base-panel2 border border-base-edge px-2 py-1.5 text-sm text-text-primary tabular"
                      value={params.reward_ratio_min}
                      onChange={(e) => handleParamChange('reward_ratio_min', parseFloat(e.target.value))}
                    />
                  </div>
                  <div>
                    <FieldLabel htmlFor="strat-risk_por_operacion" hint="% del capital">
                      Riesgo por operación
                    </FieldLabel>
                    <input
                      id="strat-risk_por_operacion"
                      type="number"
                      min={0.1}
                      max={10}
                      step={0.1}
                      className="w-full bg-base-panel2 border border-base-edge px-2 py-1.5 text-sm text-text-primary tabular"
                      value={params.risk_por_operacion}
                      onChange={(e) => handleParamChange('risk_por_operacion', parseFloat(e.target.value))}
                    />
                  </div>
                  <div>
                    <FieldLabel htmlFor="strat-slippage_pips" hint="pips">
                      Slippage
                    </FieldLabel>
                    <input
                      id="strat-slippage_pips"
                      type="number"
                      min={0}
                      max={10}
                      step={0.1}
                      className="w-full bg-base-panel2 border border-base-edge px-2 py-1.5 text-sm text-text-primary tabular"
                      value={params.slippage_pips}
                      onChange={(e) => handleParamChange('slippage_pips', parseFloat(e.target.value))}
                    />
                  </div>
                  <div>
                    <FieldLabel htmlFor="strat-comision_lote" hint="por lote">
                      Comisión
                    </FieldLabel>
                    <input
                      id="strat-comision_lote"
                      type="number"
                      min={0}
                      max={10}
                      step={0.1}
                      className="w-full bg-base-panel2 border border-base-edge px-2 py-1.5 text-sm text-text-primary tabular"
                      value={params.comision_lote}
                      onChange={(e) => handleParamChange('comision_lote', parseFloat(e.target.value))}
                    />
                  </div>
                  <div className="flex flex-wrap items-end gap-4">
                    <label
                      htmlFor="strat-usar_kill_zones"
                      className="flex items-center gap-1.5 font-condensed text-[11px] tracking-[0.12em] uppercase text-text-secondary"
                    >
                      <input
                        id="strat-usar_kill_zones"
                        type="checkbox"
                        checked={params.usar_kill_zones}
                        onChange={(e) => handleParamChange('usar_kill_zones', e.target.checked)}
                        className="w-3.5 h-3.5 accent-brand-cyan"
                      />
                      Usar kill zones
                    </label>
                    <label
                      htmlFor="strat-usar_trend_d1"
                      className="flex items-center gap-1.5 font-condensed text-[11px] tracking-[0.12em] uppercase text-text-secondary"
                    >
                      <input
                        id="strat-usar_trend_d1"
                        type="checkbox"
                        checked={params.usar_trend_d1}
                        onChange={(e) => handleParamChange('usar_trend_d1', e.target.checked)}
                        className="w-3.5 h-3.5 accent-brand-cyan"
                      />
                      Usar trend D1
                    </label>
                    <Button variant="ghost" size="sm" icon="refresh" onClick={handleResetParams}>
                      Restablecer
                    </Button>
                  </div>
                </div>
              </Panel>
            )}
          </div>
        </div>

        <aside className="xl:w-64 shrink-0 mt-4 xl:mt-0 space-y-3">
          <DetectorReadout activos={detectoresActivos} />

          <Panel title="Contexto de sesión">
            <dl className="space-y-2">
              <div className="flex justify-between items-center gap-3">
                <dt className="font-condensed text-[10px] tracking-[0.14em] uppercase text-text-secondary">
                  Sesión
                </dt>
                <dd className="font-mono text-[11px] text-text-primary tabular">
                  {asset?.session || '—'}
                </dd>
              </div>
              <div className="flex justify-between items-center gap-3">
                <dt className="font-condensed text-[10px] tracking-[0.14em] uppercase text-text-secondary">
                  Kill zone
                </dt>
                <dd className="font-mono text-[11px] text-text-primary tabular">
                  {asset?.kill_zone || '—'}
                </dd>
              </div>
              <div className="flex justify-between items-center gap-3">
                <dt className="font-condensed text-[10px] tracking-[0.14em] uppercase text-text-secondary">
                  Detectores
                </dt>
                <dd className="font-mono text-[11px] text-brand-cyan tabular">
                  {detectoresActivos.length} / 6
                </dd>
              </div>
            </dl>
          </Panel>

          <Panel title="Notificaciones ntfy">
            <AssetNtfyForm simbolo={simbolo!} compact />
            <p className="text-[10px] leading-relaxed text-text-muted pt-2 mt-2 border-t border-base-line">
              Las notificaciones se envían tanto en modo replay como con Deriv conectado.
            </p>
          </Panel>
        </aside>
      </div>
    </div>
  )
}
