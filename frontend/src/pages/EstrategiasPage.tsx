import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchStrategies, fetchAssets } from '../api'
import {
  Badge,
  EmptyState,
  ErrorState,
  PageHeader,
  Panel,
  QueryState,
  SectionTitle,
  SkeletonCard,
} from '../components/ui'
import { fmtNum } from '../utils/format'

interface ParamSchema {
  tipo: string
  default: any
  min?: number
  max?: number
  label?: string
  descripcion?: string
  grupo?: string
  opciones?: string[]
}

function fmtValor(tipo: string, v: unknown): string {
  if (v === undefined || v === null || v === '') return '—'
  if (tipo === 'bool') return v ? 'true' : 'false'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : fmtNum(v, 3)
  return String(v)
}

function Parametros({ schema }: { schema: Record<string, ParamSchema> }) {
  const entradas = Object.entries(schema)
  if (entradas.length === 0) {
    return <p className="text-[11px] text-text-muted">Esta estrategia no expone parámetros.</p>
  }

  return (
    <div className="border border-base-line overflow-x-auto">
      <table className="w-full border-collapse text-[11px]">
        <caption className="sr-only">Parámetros de la estrategia</caption>
        <thead>
          <tr>
            <th scope="col" className="sticky top-0 bg-base-panel2 border-b border-base-line px-2.5 py-1.5 text-left font-condensed text-[10px] font-semibold tracking-[0.12em] uppercase text-text-muted">
              Parámetro
            </th>
            <th scope="col" className="sticky top-0 bg-base-panel2 border-b border-base-line px-2.5 py-1.5 text-left font-condensed text-[10px] font-semibold tracking-[0.12em] uppercase text-text-muted">
              Tipo
            </th>
            <th scope="col" className="sticky top-0 bg-base-panel2 border-b border-base-line px-2.5 py-1.5 text-right font-condensed text-[10px] font-semibold tracking-[0.12em] uppercase text-text-muted">
              Defecto
            </th>
            <th scope="col" className="sticky top-0 bg-base-panel2 border-b border-base-line px-2.5 py-1.5 text-left font-condensed text-[10px] font-semibold tracking-[0.12em] uppercase text-text-muted">
              Rango
            </th>
          </tr>
        </thead>
        <tbody>
          {entradas.map(([k, s]) => (
            <tr key={k} className="border-b border-base-line/60">
              <td className="px-2.5 py-1.5 text-text-primary">
                <div className="font-mono">{s.label || k}</div>
                {s.grupo && (
                  <div className="font-condensed text-[10px] uppercase tracking-wider text-text-muted">{s.grupo}</div>
                )}
              </td>
              <td className="px-2.5 py-1.5 font-mono text-text-secondary">{s.tipo}</td>
              <td className="px-2.5 py-1.5 tabular text-right font-mono text-text-primary">
                {fmtValor(s.tipo, s.default)}
              </td>
              <td className="px-2.5 py-1.5 font-mono text-text-secondary">
                {s.opciones
                  ? s.opciones.join(' | ')
                  : [s.min !== undefined ? `min ${s.min}` : '', s.max !== undefined ? `max ${s.max}` : '']
                      .filter(Boolean)
                      .join(' · ') || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function EstrategiasPage() {
  const {
    data: strategies,
    isLoading,
    error,
    refetch,
  } = useQuery({ queryKey: ['strategies'], queryFn: fetchStrategies })
  const assetsQ = useQuery({ queryKey: ['assets'], queryFn: fetchAssets })

  const nParams = (s: any) => (s.parametros ? Object.keys(s.parametros).length : 0)

  return (
    <div>
      <PageHeader
        title="Estrategias"
        eyebrow="Plugins"
        description="Estrategias registradas en el kernel: metadatos, parámetros expuestos y dónde ejecutarlas."
        actions={
          strategies && (
            <Badge tone="neutral">{strategies.length} registradas</Badge>
          )
        }
      />

      <QueryState
        loading={isLoading}
        error={error}
        onRetry={() => refetch()}
        errorTitle="No se pudieron cargar las estrategias"
        skeleton={
          <div className="space-y-3">
            <SkeletonCard />
            <SkeletonCard />
          </div>
        }
      >
        {strategies && strategies.length === 0 && (
          <EmptyState
            icon="database"
            title="Sin estrategias registradas"
            description="El plugin registry no devolvió ninguna estrategia."
          />
        )}

        <div className="space-y-3">
          {strategies?.map((s: any) => (
            <Panel
              key={s.nombre}
              title={<span className="font-mono normal-case tracking-normal text-sm text-text-primary">{s.nombre}</span>}
              subtitle={s.descripcion || 'Sin descripción'}
              actions={
                <>
                  <Badge tone="muted">v{s.version}</Badge>
                  <Badge tone="brand">{nParams(s)} params</Badge>
                </>
              }
            >
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <span className="font-condensed text-[10px] font-semibold tracking-[0.14em] uppercase text-text-muted">
                  Timeframes
                </span>
                {(s.timeframes || []).length > 0 ? (
                  s.timeframes.map((tf: string) => (
                    <Badge key={tf} tone="neutral">
                      {tf}
                    </Badge>
                  ))
                ) : (
                  <span className="text-[11px] text-text-muted">No declarados</span>
                )}
              </div>

              <SectionTitle>Parámetros expuestos</SectionTitle>
              <Parametros schema={s.parametros || {}} />

              <div className="mt-4">
                <SectionTitle
                  aside={
                    assetsQ.data && (
                      <span className="tabular text-[10px] text-text-muted">
                        {assetsQ.data.length} instrumentos
                      </span>
                    )
                  }
                >
                  Ejecutar en activo
                </SectionTitle>

                <QueryState
                  loading={assetsQ.isLoading}
                  error={assetsQ.error}
                  onRetry={() => assetsQ.refetch()}
                  errorTitle="No se pudieron cargar los activos"
                  compact
                  skeleton={<SkeletonCard />}
                  empty={<EmptyState icon="database" title="Sin activos disponibles" compact />}
                >
                  {assetsQ.data && assetsQ.data.length === 0 ? (
                    <EmptyState icon="database" title="Sin activos disponibles" compact />
                  ) : (
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
                      {assetsQ.data?.map((a: any) => (
                        <Link
                          key={a.simbolo}
                          to={`/activo/${a.simbolo}`}
                          className="font-mono text-[11px] border border-base-edge bg-base-panel2 hover:bg-base-line hover:text-text-primary text-text-secondary px-2 py-1.5 transition-colors text-center focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand-cyan"
                        >
                          {a.simbolo}
                        </Link>
                      ))}
                    </div>
                  )}
                </QueryState>
              </div>
            </Panel>
          ))}
        </div>
      </QueryState>
    </div>
  )
}
