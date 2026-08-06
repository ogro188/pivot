import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchAssets } from '../api'
import { useStore } from '../store'
import SignalCard from '../components/SignalCard'

export default function HubPage() {
  const { data: assets } = useQuery({ queryKey: ['assets'], queryFn: fetchAssets, refetchInterval: 5000 })
  const globalSignals = useStore((s) => s.globalSignals)
  const setAssets = useStore((s) => s.setAssets)

  useEffect(() => {
    if (assets) setAssets(assets)
  }, [assets, setAssets])

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Hub</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {assets?.map((a: any) => (
          <Link key={a.simbolo} to={`/activo/${a.simbolo}`}>
            <div className={`p-4 rounded-lg border transition-colors ${a.running ? 'border-green-500 bg-gray-800' : 'border-gray-700 bg-gray-800 hover:border-gray-500'}`}>
              <div className="flex justify-between">
                <span className="font-bold">{a.simbolo}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${a.running ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-400'}`}>
                  {a.running ? 'LIVE' : 'OFF'}
                </span>
              </div>
              <div className="text-sm text-gray-400 mt-1">{a.nombre}</div>
              <div className="text-lg font-mono mt-2">{a.price?.toFixed(a.decimales || 5)}</div>
              <div className="text-xs text-gray-500 mt-1">{a.session} | {a.kill_zone}</div>
            </div>
          </Link>
        ))}
      </div>
      <div>
        <h2 className="text-lg font-bold mb-3">Señales recientes</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {globalSignals.map((s) => (
            <SignalCard key={`${s.id}-${s.ts}`} signal={s} />
          ))}
          {globalSignals.length === 0 && (
            <div className="text-gray-500 text-sm">No hay señales aún. Inicia un activo para comenzar.</div>
          )}
        </div>
      </div>
    </div>
  )
}
