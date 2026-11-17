import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchAssets } from '../api'
import { useStore } from '../store'
import SignalCard from '../components/SignalCard'
import { exportSignalsToCsv } from '../utils/exportCsv'
import { expiraEn, esAltaConfianza } from '../utils/signals'
import { useNowTick } from '../hooks/useNowTick'
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  PageHeader,
  SectionTitle,
  SkeletonCard,
} from '../components/ui'

export default function HubPage() {
  const { data: assets, isLoading, error, refetch } = useQuery({
    queryKey: ['assets'],
    queryFn: fetchAssets,
    refetchInterval: 5000,
  })
  const globalSignals = useStore((s) => s.globalSignals)
  const setAssets = useStore((s) => s.setAssets)
  const liveAssets = useStore((s) => s.assets)
  const derivConnected = useStore((s) => s.derivConnected)

  useEffect(() => {
    if (assets) setAssets(assets)
  }, [assets, setAssets])

  const now = useNowTick()
  const activeSignals = globalSignals.filter((s) => expiraEn(s) > now)
  const expiredSignals = globalSignals.filter((s) => expiraEn(s) <= now)

  const runningCount = assets?.filter((a: any) => a.running).length ?? 0
  const totalSignals = globalSignals.length
  const highConviction = activeSignals.filter(esAltaConfianza).length

  const stats = [
    { label: 'Activos', value: isLoading ? '—' : String(assets?.length ?? 0) },
    { label: 'En vivo', value: isLoading ? '—' : String(runningCount) },
    { label: 'Señales activas', value: String(activeSignals.length) },
    { label: 'Convicción alta', value: String(highConviction) },
    { label: 'Acumuladas', value: String(totalSignals) },
  ]

  return (
    <div>
      <PageHeader
        title="Hub"
        eyebrow="Panel general"
        description="Estado de los instrumentos y flujo de señales en tiempo real."
        actions={
          <>
            <Badge tone={derivConnected ? 'brand' : 'muted'} title="Estado de la conexión Deriv">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  derivConnected ? 'bg-brand-cyan animate-pulse-dot' : 'bg-text-muted'
                }`}
              />
              Deriv {derivConnected ? 'ON' : 'OFF'}
            </Badge>
            <Button
              variant="secondary"
              icon="download"
              onClick={() => exportSignalsToCsv(globalSignals)}
              disabled={globalSignals.length === 0}
            >
              Exportar CSV
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-px bg-base-line border border-base-line mb-5">
        {stats.map((s) => (
          <div key={s.label} className="bg-base-panel px-3 py-2.5">
            <div className="font-condensed text-[10px] font-semibold tracking-[0.14em] uppercase text-text-muted">
              {s.label}
            </div>
            <div className="tabular font-mono text-lg text-text-primary mt-0.5">{s.value}</div>
          </div>
        ))}
      </div>

      <SectionTitle
        aside={
          assets && (
            <span className="tabular text-[10px] text-text-muted">{assets.length} instrumentos</span>
          )
        }
      >
        Instrumentos
      </SectionTitle>

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}
      {error && (
        <ErrorState
          title="No se pudieron cargar los instrumentos"
          message={error}
          onRetry={() => refetch()}
        />
      )}
      {assets && assets.length === 0 && (
        <EmptyState
          icon="database"
          title="Sin instrumentos"
          description="No hay activos configurados en el sistema."
        />
      )}
      {assets && assets.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {assets.map((a: any) => {
            const live = liveAssets[a.simbolo]
            const price = live?.price ?? a.price
            const isDeriv = a.fuente === 'deriv'
            const derivOn = !!a.deriv_connected
            const up =
              live?.price != null && a.price != null ? (live.price > a.price ? 1 : live.price < a.price ? -1 : 0) : 0
            return (
              <Link key={a.simbolo} to={`/activo/${a.simbolo}`} className="group block">
                <div
                  className={`panel p-3 h-full transition-colors group-hover:border-base-edge ${
                    a.running ? 'border-brand-cyan/40' : ''
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="font-mono font-semibold text-sm text-text-primary truncate">
                        {a.simbolo}
                      </div>
                      <div className="font-condensed text-[10px] tracking-[0.12em] uppercase text-text-muted truncate">
                        {a.nombre}
                      </div>
                    </div>
                    <Badge tone={a.running ? 'brand' : 'muted'}>{a.running ? 'LIVE' : 'OFF'}</Badge>
                  </div>

                  <div
                    className={`tabular font-mono text-xl mt-2 ${
                      up === 1 ? 'text-signal-long' : up === -1 ? 'text-signal-short' : 'text-text-primary'
                    }`}
                  >
                    {price != null ? price.toFixed(a.decimales || 5) : '—'}
                  </div>

                  <div className="flex flex-wrap items-center gap-1.5 mt-2 pt-2 border-t border-base-line">
                    <span className="font-condensed text-[10px] tracking-[0.1em] uppercase text-text-muted">
                      {a.session || '—'} · {a.kill_zone || '—'}
                    </span>
                    {isDeriv && (
                      <span
                        className={`ml-auto font-condensed text-[9px] tracking-[0.12em] uppercase border px-1 py-px ${
                          derivOn
                            ? 'text-brand-cyan border-brand-cyan/40 bg-brand-cyan/10'
                            : 'text-text-muted border-base-line'
                        }`}
                      >
                        Deriv {derivOn ? 'ON' : 'OFF'}
                      </span>
                    )}
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      )}

      <div className="mt-6">
        <SectionTitle
          aside={
            <span className="tabular text-[10px] text-text-muted">{activeSignals.length} abiertas</span>
          }
        >
          Señales activas
        </SectionTitle>
        {activeSignals.length === 0 ? (
          <EmptyState
            icon="activity"
            title="No hay señales activas"
            description="Cuando un detector dispare una señal válida aparecerá acá con su cuenta regresiva."
            compact
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
            {activeSignals.map((s) => (
              <SignalCard key={`${s.id}-${s.ts}`} signal={s} variant="active" />
            ))}
          </div>
        )}
      </div>

      {expiredSignals.length > 0 && (
        <div className="mt-6">
          <SectionTitle
            aside={
              <span className="tabular text-[10px] text-text-muted">
                {expiredSignals.length} expiradas
              </span>
            }
          >
            Señales expiradas
          </SectionTitle>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
            {expiredSignals.slice(0, 20).map((s) => (
              <SignalCard key={`${s.id}-${s.ts}`} signal={s} variant="expired" />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
