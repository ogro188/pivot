import { useEffect, useState } from 'react'
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
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Hub</h1>
        <button onClick={handleExport} className="bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded text-sm flex items-center gap-1">
          📥 Exportar CSV
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {assets?.map((a: any) => {
          const live = liveAssets[a.simbolo]
          const price = live?.price ?? a.price
          return (
            <Link key={a.simbolo} to={`/activo/${a.simbolo}`}>
              <div className={`p-4 rounded-lg border transition-colors ${a.running ? 'border-green-500 bg-gray-800' : 'border-gray-700 bg-gray-800 hover:border-gray-500'}`}>
                <div className="flex justify-between">
                  <span className="font-bold">{a.simbolo}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${a.running ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-400'}`}>
                    {a.running ? 'LIVE' : 'OFF'}
                  </span>
                </div>
                <div className="text-sm text-gray-400 mt-1">{a.nombre}</div>
                <div className="text-lg font-mono mt-2">{price != null ? price.toFixed(a.decimales || 5) : '—'}</div>
                <div className="text-xs text-gray-500 mt-1">{a.session} | {a.kill_zone}</div>
              </div>
            </Link>
          )
        })}
      </div>
      <div>
        <h2 className="text-lg font-bold mb-3">Señales activas</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {activeSignals.map((s) => (
            <SignalCountdown key={`${s.id}-${s.ts}`} signal={s} />
          ))}
          {activeSignals.length === 0 && (
            <div className="text-gray-500 text-sm col-span-full">No hay señales activas.</div>
          )}
        </div>
      </div>
      {expiredSignals.length > 0 && (
        <div className="mt-6">
          <h2 className="text-lg font-bold mb-3 text-gray-500">Señales expiradas</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {expiredSignals.slice(0, 20).map((s) => (
              <SignalCountdown key={`${s.id}-${s.ts}`} signal={s} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
