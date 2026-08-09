import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchAssets } from '../api'
import { useStore } from '../store'
import SignalCard from '../components/SignalCard'
import SignalCountdown from '../components/SignalCountdown'
import { exportSignalsToCsv } from '../utils/exportCsv'

export default function HubPage() {
  const { data: assets } = useQuery({ queryKey: ['assets'], queryFn: fetchAssets, refetchInterval: 5000 })
  const globalSignals = useStore((s) => s.globalSignals)
  const setAssets = useStore((s) => s.setAssets)
  const liveAssets = useStore((s) => s.assets)

  useEffect(() => {
    if (assets) setAssets(assets)
  }, [assets, setAssets])

  // Separar señales activas y expiradas
  const now = Date.now()
  const activeSignals = globalSignals.filter((s) => {
    const timeframe = s.timeframe || 'M15'
    const minutesPerCandle = timeframe === 'M15' ? 15 : timeframe === 'H1' ? 60 : timeframe === 'H4' ? 240 : 1440
    const expirationMs = (s.ts || 0) + s.expiracion_velas * minutesPerCandle * 60 * 1000
    return expirationMs > now
  })
  const expiredSignals = globalSignals.filter((s) => {
    const timeframe = s.timeframe || 'M15'
    const minutesPerCandle = timeframe === 'M15' ? 15 : timeframe === 'H1' ? 60 : timeframe === 'H4' ? 240 : 1440
    const expirationMs = (s.ts || 0) + s.expiracion_velas * minutesPerCandle * 60 * 1000
    return expirationMs <= now
  })

  const handleExport = () => {
    exportSignalsToCsv(globalSignals)
  }

  return (
    <div className="space-y-5">
      <div className="flex justify-between items-center">
        <h1 className="font-condensed text-[13px] tracking-widest text-text-muted uppercase">Hub</h1>
        <button onClick={handleExport} className="border border-base-line bg-base-panel hover:bg-base-panel2 px-3 py-1 font-condensed text-[11px] tracking-widest uppercase text-text-secondary transition-colors">
          📥 Exportar CSV
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {assets?.map((a: any) => {
          const live = liveAssets[a.simbolo]
          const price = live?.price ?? a.price
          return (
            <Link key={a.simbolo} to={`/activo/${a.simbolo}`}>
              <div className={`panel p-2.5 transition-colors ${a.running ? 'border-brand-cyan/40' : 'hover:border-base-line'}`}>
                <div className="flex justify-between">
                  <span className="font-mono font-semibold text-sm text-text-primary">{a.simbolo}</span>
                  <span className={`font-condensed text-[10px] px-1.5 py-0.5 tracking-widest ${a.running ? 'bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/40' : 'bg-base-panel2 text-text-muted border border-base-line'}`}>
                    {a.running ? 'LIVE' : 'OFF'}
                  </span>
                </div>
                <div className="font-condensed text-[11px] text-text-secondary mt-0.5">{a.nombre}</div>
                <div className="tabular text-lg text-text-primary mt-1">{price != null ? price.toFixed(a.decimales || 5) : '—'}</div>
                <div className="font-condensed text-[10px] text-text-muted mt-0.5 normal-case">{a.session} | {a.kill_zone}</div>
              </div>
            </Link>
          )
        })}
      </div>
      <div>
        <h2 className="font-condensed text-[11px] tracking-widest uppercase text-text-muted mb-2">Señales activas</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {activeSignals.map((s) => (
            <SignalCountdown key={`${s.id}-${s.ts}`} signal={s} />
          ))}
          {activeSignals.length === 0 && (
            <div className="text-text-muted text-sm col-span-full">No hay señales activas.</div>
          )}
        </div>
      </div>
      {expiredSignals.length > 0 && (
        <div className="mt-4">
          <h2 className="font-condensed text-[11px] tracking-widest uppercase text-text-muted mb-2">Señales expiradas</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {expiredSignals.slice(0, 20).map((s) => (
              <SignalCountdown key={`${s.id}-${s.ts}`} signal={s} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}