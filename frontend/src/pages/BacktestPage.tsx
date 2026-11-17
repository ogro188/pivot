import { useMemo, useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  fetchAssets,
  fetchStrategies,
  runBacktest,
  fetchBacktests,
  type BacktestRequest,
  type BacktestSummary,
} from '../api'
import ParamForm from '../components/ParamForm'
import {
  Badge,
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  FieldLabel,
  PageHeader,
  Panel,
  QueryState,
  SectionTitle,
  SkeletonCard,
  useToast,
} from '../components/ui'
import type { OperacionBacktestDTO } from '../api'
import type { Column } from '../components/ui'
import { STATE_OK, STATE_ERROR, BASE_LINE, TEXT_MUTED } from '../theme'
import { fmtDate, fmtDateTime, fmtMoney, fmtPct, fmtNum, toNumber } from '../utils/format'
import { describeError } from '../utils/errors'

function errorDetail(err: unknown): string {
  const e = err as any
  const detail = e?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) return detail[0]?.msg || 'Error de validación'
  return describeError(err)
}

type Resultado = {
  status?: string
  estrategia?: string
  activo?: string
  timeframe?: string
  fecha_inicio?: string
  fecha_fin?: string
  n_senales?: number
  capital_inicial?: number
  capital_final?: number
  equity?: [number, number][]
  operaciones?: OperacionBacktestDTO[]
  total_operaciones?: number
  winrate?: number
  profit_factor?: number
  sharpe_ratio?: number
  retorno_total?: number
  drawdown_maximo?: number
}

function Kpi({ label, value, tone }: { label: string; value: string; tone?: 'ok' | 'warn' | 'error' }) {
  const color =
    tone === 'ok'
      ? 'text-state-ok'
      : tone === 'warn'
        ? 'text-state-warn'
        : tone === 'error'
          ? 'text-state-error'
          : 'text-text-primary'
  return (
    <div className="bg-base-panel2 border border-base-line px-2.5 py-2">
      <div className="font-condensed text-[10px] font-semibold tracking-[0.14em] uppercase text-text-muted">
        {label}
      </div>
      <div className={`tabular font-mono text-lg mt-0.5 ${color}`}>{value}</div>
    </div>
  )
}

function EquityChart({ equity, capital }: { equity: [number, number][]; capital?: number }) {
  if (!equity || equity.length < 2) return null

  const vals = equity.map(([, v]) => v)
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const range = max - min || 1
  const last = equity.length - 1

  const toY = (v: number) => 100 - ((v - min) / range) * 100
  const line = equity.map(([, v], i) => `${(i / last) * 100},${toY(v)}`).join(' ')
  const area = `0,${toY(vals[0])} ${line} 100,${toY(vals[last])}`

  const capitalY = capital != null && capital >= min && capital <= max ? toY(capital) : null
  const terminoEnGanancia = vals[last] >= vals[0]
  const color = terminoEnGanancia ? STATE_OK : STATE_ERROR

  return (
    <figure className="mt-3">
      <figcaption className="flex items-center justify-between gap-3 mb-1.5">
        <span className="font-condensed text-[10px] font-semibold tracking-[0.14em] uppercase text-text-muted">
          Curva de equity
        </span>
        <span className="font-mono text-[10px] text-text-muted tabular">
          {fmtDateTime(equity[0][0])} → {fmtDateTime(equity[last][0])}
        </span>
      </figcaption>

      <div className="relative border border-base-line bg-base-panel2">
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="block w-full h-40"
          role="img"
          aria-label={`Curva de equity con ${equity.length} puntos. Máximo ${fmtMoney(max)}, mínimo ${fmtMoney(min)}.`}
        >
          {[25, 50, 75].map((y) => (
            <line key={y} x1="0" y1={y} x2="100" y2={y} stroke={BASE_LINE} strokeWidth="0.4" vectorEffect="non-scaling-stroke" />
          ))}
          {capitalY !== null && (
            <line
              x1="0"
              y1={capitalY}
              x2="100"
              y2={capitalY}
              stroke={TEXT_MUTED}
              strokeWidth="1"
              strokeDasharray="4 4"
              vectorEffect="non-scaling-stroke"
            />
          )}
          <polygon points={area} fill={color} opacity="0.1" />
          <polyline
            points={line}
            fill="none"
            stroke={color}
            strokeWidth="1.5"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>

        <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-1">
          <span className="self-start font-mono text-[9px] tabular text-text-muted bg-base-panel/80 px-1">
            {fmtMoney(max)}
          </span>
          <span className="self-start font-mono text-[9px] tabular text-text-muted bg-base-panel/80 px-1">
            {fmtMoney(min)}
          </span>
        </div>
      </div>
    </figure>
  )
}

const OP_COLS: Column<OperacionBacktestDTO>[] = [
  { key: 'id', header: '#', width: '48px', numeric: true, sortValue: (r) => Number(r.id) || 0 },
  { key: 'direccion', header: 'Dir.', width: '62px', render: (r) => <Badge tone={r.direccion === 1 ? 'long' : 'short'}>{r.direccion === 1 ? 'LONG' : 'SHORT'}</Badge> },
  { key: 'precio_entrada', header: 'Entrada', numeric: true, sortable: true, sortValue: (r) => Number(r.precio_entrada) || 0, render: (r) => fmtNum(r.precio_entrada, 5) },
  { key: 'precio_salida', header: 'Salida', numeric: true, sortable: true, sortValue: (r) => Number(r.precio_salida) || 0, render: (r) => (r.precio_salida != null ? fmtNum(r.precio_salida, 5) : '—') },
  { key: 'razon_salida', header: 'Salida', render: (r) => r.razon_salida || '—' },
  { key: 'velas_en_operacion', header: 'Velas', numeric: true, sortable: true, sortValue: (r) => r.velas_en_operacion || 0 },
  { key: 'pnl_dinero', header: 'PnL', numeric: true, sortable: true, sortValue: (r) => r.pnl_dinero, render: (r) => <span className={r.pnl_dinero >= 0 ? 'text-state-ok' : 'text-signal-short'}>{fmtMoney(r.pnl_dinero)}</span> },
]

export default function BacktestPage() {
  const toast = useToast()
  const { data: assets, isLoading: assetsLoading, error: assetsError, refetch: refetchAssets } = useQuery({
    queryKey: ['assets'],
    queryFn: fetchAssets,
  })
  const { data: strategies } = useQuery({ queryKey: ['strategies'], queryFn: fetchStrategies })
  const history = useQuery({ queryKey: ['backtests'], queryFn: () => fetchBacktests(), staleTime: 0 })

  const [asset, setAsset] = useState('')
  const [strategy, setStrategy] = useState('')
  const [timeframe, setTimeframe] = useState('M15')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [params, setParams] = useState<Record<string, any>>({})

  const stratObj = strategies?.find((s: any) => s.nombre === strategy)

  const mutation = useMutation({
    mutationFn: runBacktest,
    onSuccess: () => {
      toast.success('La corrida terminó y quedó registrada en el historial.', 'Backtest completado')
      history.refetch()
    },
    onError: (err) => toast.error(errorDetail(err), 'No se pudo ejecutar el backtest'),
  })

  const resultado = mutation.data as Resultado | undefined
  const [historico, setHistorico] = useState<BacktestSummary | null>(null)
  const ver = historico ?? null

  const formError = mutation.isError ? errorDetail(mutation.error) : null
  const faltan = !asset || !strategy || !desde || !hasta

  const handleSubmit = () => {
    if (faltan) return
    setHistorico(null)
    const body: BacktestRequest = {
      estrategia: strategy,
      activo: asset,
      timeframe,
      fecha_inicio: desde.slice(0, 10),
      fecha_fin: hasta.slice(0, 10),
      capital_inicial: 10000,
      riesgo_por_operacion: 0.01,
      parametros: params,
    }
    mutation.mutate(body)
  }

  const ops = resultado?.operaciones ?? []
  const equity = resultado?.equity ?? []

  const operacionesGanadoras = useMemo(() => ops.filter((o) => o.pnl_dinero > 0).length, [ops])

  const histCols: Column<BacktestSummary>[] = [
    { key: 'id', header: 'ID', width: '52px', numeric: true, sortValue: (r) => r.id },
    { key: 'estrategia', header: 'Estrategia', sortable: true, sortValue: (r) => r.estrategia || '', render: (r) => r.estrategia || '—' },
    { key: 'simbolo', header: 'Activo', width: '90px', render: (r) => r.simbolo || '—' },
    { key: 'timeframe', header: 'TF', width: '56px', render: (r) => r.timeframe || '—' },
    { key: 'created_at', header: 'Ejecutado', sortable: true, sortValue: (r) => r.created_at || '', render: (r) => fmtDateTime(r.created_at) },
    { key: 'total_operaciones', header: 'Ops', numeric: true, sortable: true, sortValue: (r) => r.total_operaciones ?? 0 },
    { key: 'win_rate', header: 'Winrate', numeric: true, sortable: true, sortValue: (r) => r.win_rate ?? -1, render: (r) => fmtPct(r.win_rate) },
    { key: 'retorno_total', header: 'Retorno', numeric: true, sortable: true, sortValue: (r) => r.retorno_total ?? -9999, render: (r) => <span className={(r.retorno_total ?? 0) >= 0 ? 'text-state-ok' : 'text-signal-short'}>{fmtPct(r.retorno_total)}</span> },
    { key: 'drawdown_max', header: 'MDD', numeric: true, sortable: true, sortValue: (r) => r.drawdown_max ?? -1, render: (r) => fmtPct(r.drawdown_max) },
    { key: 'profit_factor', header: 'PF', numeric: true, sortable: true, sortValue: (r) => r.profit_factor ?? -1, render: (r) => fmtNum(r.profit_factor, 2) },
  ]

  return (
    <div>
      <PageHeader
        title="Backtest"
        eyebrow="Laboratorio"
        description="Ejecuta una estrategia sobre datos históricos y revisa el registro de corridas anteriores."
        actions={
          <Button
            icon="refresh"
            onClick={() => history.refetch()}
            loading={history.isFetching && !history.data}
          >
            Actualizar historial
          </Button>
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 items-start">
        <Panel
          title="Nueva corrida"
          subtitle="El rango de fechas debe caer dentro del CSV disponible."
        >
          <QueryState
            loading={assetsLoading}
            error={assetsError}
            onRetry={() => refetchAssets()}
            errorTitle="No se pudieron cargar los activos"
            skeleton={<SkeletonCard />}
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <FieldLabel htmlFor="bt-asset">Activo</FieldLabel>
                <select
                  id="bt-asset"
                  className="w-full bg-base-panel2 border border-base-line px-2 h-8 text-sm text-text-primary focus:border-base-edge focus:outline-none"
                  value={asset}
                  onChange={(e) => setAsset(e.target.value)}
                >
                  <option value="">Seleccionar...</option>
                  {assets?.map((a: any) => (
                    <option key={a.simbolo} value={a.simbolo}>
                      {a.simbolo}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <FieldLabel htmlFor="bt-strategy">Estrategia</FieldLabel>
                <select
                  id="bt-strategy"
                  className="w-full bg-base-panel2 border border-base-line px-2 h-8 text-sm text-text-primary focus:border-base-edge focus:outline-none"
                  value={strategy}
                  onChange={(e) => setStrategy(e.target.value)}
                >
                  <option value="">Seleccionar...</option>
                  {strategies?.map((s: any) => (
                    <option key={s.nombre} value={s.nombre}>
                      {s.nombre}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <FieldLabel htmlFor="bt-timeframe">Timeframe</FieldLabel>
                <select
                  id="bt-timeframe"
                  className="w-full bg-base-panel2 border border-base-line px-2 h-8 text-sm text-text-primary focus:border-base-edge focus:outline-none"
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value)}
                >
                  {['M15', 'H1', 'H4', 'D1'].map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <FieldLabel htmlFor="bt-desde">Desde</FieldLabel>
                  <input
                    id="bt-desde"
                    type="date"
                    className="w-full bg-base-panel2 border border-base-line px-2 h-8 text-sm text-text-primary tabular focus:border-base-edge focus:outline-none"
                    value={desde}
                    onChange={(e) => setDesde(e.target.value)}
                  />
                </div>
                <div>
                  <FieldLabel htmlFor="bt-hasta">Hasta</FieldLabel>
                  <input
                    id="bt-hasta"
                    type="date"
                    className="w-full bg-base-panel2 border border-base-line px-2 h-8 text-sm text-text-primary tabular focus:border-base-edge focus:outline-none"
                    value={hasta}
                    onChange={(e) => setHasta(e.target.value)}
                  />
                </div>
              </div>
            </div>

            {stratObj?.parametros && Object.keys(stratObj.parametros).length > 0 && (
              <div className="mt-4 space-y-3">
                <SectionTitle>Parámetros</SectionTitle>
                <ParamForm
                  schema={stratObj.parametros}
                  values={params}
                  onChange={(k, v) => setParams((p) => ({ ...p, [k]: v }))}
                  onSubmit={handleSubmit}
                  loading={mutation.isPending}
                  hideSubmit
                />
              </div>
            )}

            <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-base-line pt-3">
              <Button variant="primary" icon="activity" onClick={handleSubmit} loading={mutation.isPending}>
                {mutation.isPending ? 'Ejecutando…' : 'Ejecutar backtest'}
              </Button>
              {faltan && (
                <span className="font-mono text-[10px] text-text-muted">
                  Completa activo, estrategia y rango de fechas.
                </span>
              )}
            </div>

            {formError && <div className="mt-3"><ErrorState title="La corrida falló" message={formError} /></div>}
          </QueryState>
        </Panel>

        <div className="space-y-4">
          <Panel
            title="Resultado"
            subtitle={
              ver
                ? `Corrida #${ver.id} — ${fmtDateTime(ver.created_at)}`
                : resultado
                  ? `${resultado.estrategia} · ${resultado.activo} · ${resultado.timeframe}`
                  : undefined
            }
            actions={
              ver && (
                <Button size="sm" variant="ghost" icon="close" onClick={() => setHistorico(null)}>
                  Cerrar
                </Button>
              )
            }
          >
            {!ver && !resultado && !mutation.isPending && (
              <EmptyState
                icon="chart"
                title="Sin corrida seleccionada"
                description="Completa el formulario y ejecuta un backtest, o abre una corrida desde el historial."
                compact
              />
            )}

            {mutation.isPending && (
              <div className="space-y-3">
                <SkeletonCard />
                <SkeletonCard />
              </div>
            )}

            {ver && (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge tone="brand">{ver.estrategia}</Badge>
                  <Badge tone="neutral">{ver.simbolo}</Badge>
                  <Badge tone="muted">{ver.timeframe}</Badge>
                  <Badge tone="muted">
                    {fmtDate(ver.fecha_inicio)} → {fmtDate(ver.fecha_fin)}
                  </Badge>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <Kpi label="Operaciones" value={String(ver.total_operaciones ?? 0)} />
                  <Kpi label="Winrate" value={fmtPct(ver.win_rate)} tone={(ver.win_rate ?? 0) >= 50 ? 'ok' : 'warn'} />
                  <Kpi label="Retorno" value={fmtPct(ver.retorno_total)} tone={(ver.retorno_total ?? 0) >= 0 ? 'ok' : 'error'} />
                  <Kpi label="Drawdown" value={fmtPct(ver.drawdown_max)} />
                  <Kpi label="Profit factor" value={fmtNum(ver.profit_factor, 2)} />
                  <Kpi label="Sharpe" value={fmtNum(ver.sharpe_ratio, 2)} />
                  <Kpi label="Capital inicial" value={fmtMoney(ver.capital_inicial)} />
                  <Kpi label="Capital final" value={fmtMoney(ver.capital_final)} tone={(ver.capital_final ?? 0) >= (ver.capital_inicial ?? 0) ? 'ok' : 'error'} />
                </div>

                {Object.keys(ver.metricas || {}).length > 0 && (
                  <dl className="text-[11px] text-text-secondary grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 border-t border-base-line pt-2">
                    {Object.entries(ver.metricas)
                      .filter(([k, v]) => typeof v === 'number' || typeof v === 'string')
                      .map(([k, v]) => (
                        <div key={k} className="flex justify-between gap-3 border-b border-base-line/50 py-0.5">
                          <dt className="font-condensed uppercase tracking-wider text-text-muted">{k}</dt>
                          <dd className="tabular font-mono text-text-secondary">
                            {typeof v === 'number' ? fmtNum(v, 2) : String(v)}
                          </dd>
                        </div>
                      ))}
                  </dl>
                )}

                <p className="text-[11px] text-text-muted border border-dashed border-base-line px-2.5 py-1.5">
                  La curva de equity y el detalle de operaciones solo existen para la corrida en curso.
                </p>
              </div>
            )}

            {!ver && resultado && mutation.isSuccess && (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge tone="ok">{resultado.status || 'completed'}</Badge>
                  <Badge tone="brand">{resultado.estrategia}</Badge>
                  <Badge tone="neutral">{resultado.activo}</Badge>
                  <Badge tone="muted">{resultado.timeframe}</Badge>
                  <Badge tone="muted">
                    {fmtDate(resultado.fecha_inicio)} → {fmtDate(resultado.fecha_fin)}
                  </Badge>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <Kpi label="Operaciones" value={String(resultado.total_operaciones ?? 0)} />
                  <Kpi label="Winrate" value={fmtPct(resultado.winrate)} tone={(resultado.winrate ?? 0) >= 50 ? 'ok' : 'warn'} />
                  <Kpi label="Retorno" value={fmtPct(resultado.retorno_total)} tone={(resultado.retorno_total ?? 0) >= 0 ? 'ok' : 'error'} />
                  <Kpi label="Drawdown" value={fmtPct(resultado.drawdown_maximo)} />
                  <Kpi label="Profit factor" value={fmtNum(resultado.profit_factor, 2)} />
                  <Kpi label="Sharpe" value={fmtNum(resultado.sharpe_ratio, 2)} />
                  <Kpi label="Capital final" value={fmtMoney(resultado.capital_final)} tone={(toNumber(resultado.capital_final) ?? 0) >= (toNumber(resultado.capital_inicial) ?? 0) ? 'ok' : 'error'} />
                  <Kpi label="Señales" value={String(resultado.n_senales ?? 0)} />
                </div>

                <EquityChart equity={equity} capital={resultado.capital_inicial} />

                <div className="flex flex-wrap items-center gap-4 text-[11px] text-text-secondary border-t border-base-line pt-2">
                  <span>
                    Ganadoras <span className="text-state-ok tabular font-mono">{operacionesGanadoras}</span>
                  </span>
                  <span>
                    Perdedoras <span className="text-signal-short tabular font-mono">{ops.length - operacionesGanadoras}</span>
                  </span>
                  <span>
                    Datos <span className="tabular font-mono">{ops.length}</span>
                  </span>
                </div>

                <DataTable
                  columns={OP_COLS}
                  rows={ops}
                  rowKey={(r) => String(r.id)}
                  caption="Operaciones de la corrida actual"
                  dense
                  maxHeight={340}
                  initialSort={{ key: 'id', dir: 'asc' }}
                  empty={<EmptyState icon="database" title="Sin operaciones" description="La corrida no abrió operaciones en este rango." compact />}
                />
              </div>
            )}
          </Panel>
        </div>
      </div>

      <div className="mt-6">
        <SectionTitle
          aside={
            history.data && (
              <span className="tabular text-[10px] text-text-muted">{history.data.length} corridas</span>
            )
          }
        >
          Historial
        </SectionTitle>

        <QueryState
          loading={history.isLoading}
          error={history.error}
          onRetry={() => history.refetch()}
          errorTitle="No se pudo cargar el historial"
          skeleton={<SkeletonCard />}
        >
          <DataTable
            columns={histCols}
            rows={history.data ?? []}
            rowKey={(r) => String(r.id)}
            caption="Historial de backtests"
            dense
            maxHeight={420}
            initialSort={{ key: 'id', dir: 'desc' }}
            onRowClick={(r) => {
              setHistorico(r)
              setAsset(r.simbolo || asset)
              setStrategy(r.estrategia || strategy)
              if (r.timeframe) setTimeframe(r.timeframe)
            }}
            isRowSelected={(r) => ver?.id === r.id}
            empty={
              <EmptyState
                icon="database"
                title="Aún no hay corridas guardadas"
                description="Las corridas que ejecutes se persisten en SQLite y aparecen acá para compararlas."
              />
            }
          />
        </QueryState>
      </div>
    </div>
  )
}
