import { useQuery } from '@tanstack/react-query'
import { fetchStrategies, fetchAssets } from '../api'

export default function EstrategiasPage() {
  const { data: strategies } = useQuery({ queryKey: ['strategies'], queryFn: fetchStrategies })
  const { data: assets } = useQuery({ queryKey: ['assets'], queryFn: fetchAssets })

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Estrategias</h1>
      <div className="space-y-4">
        {strategies?.map((s: any) => (
          <div key={s.nombre} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex justify-between items-center">
              <div>
                <div className="font-bold">{s.nombre} <span className="text-xs text-gray-400">v{s.version}</span></div>
                <div className="text-sm text-gray-400">{s.descripcion || 'Sin descripción'}</div>
                <div className="text-xs text-gray-500 mt-1">TFs: {s.timeframes?.join(', ')}</div>
              </div>
            </div>
            <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2">
              {assets?.map((a: any) => (
                <button key={a.simbolo} className="text-xs bg-gray-700 hover:bg-gray-600 rounded px-2 py-1 transition-colors">
                  {a.simbolo}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
