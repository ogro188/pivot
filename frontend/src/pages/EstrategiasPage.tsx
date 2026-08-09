import { useQuery } from '@tanstack/react-query'
import { fetchStrategies, fetchAssets } from '../api'

export default function EstrategiasPage() {
  const { data: strategies } = useQuery({ queryKey: ['strategies'], queryFn: fetchStrategies })
  const { data: assets } = useQuery({ queryKey: ['assets'], queryFn: fetchAssets })

  return (
    <div className="space-y-5">
      <h1 className="font-condensed text-[13px] tracking-widest text-text-muted uppercase">Estrategias</h1>
      <div className="space-y-3">
        {strategies?.map((s: any) => (
          <div key={s.nombre} className="panel p-3">
            <div className="flex justify-between items-center">
              <div>
                <div className="font-mono font-semibold text-sm text-text-primary">{s.nombre} <span className="font-condensed text-[11px] text-text-muted">v{s.version}</span></div>
                <div className="font-condensed text-[11px] text-text-secondary mt-0.5 normal-case">{s.descripcion || 'Sin descripción'}</div>
                <div className="font-mono text-[10px] text-text-muted mt-1">TFs: {s.timeframes?.join(', ')}</div>
              </div>
            </div>
            <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2">
              {assets?.map((a: any) => (
                <button key={a.simbolo} className="font-mono text-[11px] border border-base-line bg-base-panel2 hover:bg-base-line text-text-secondary px-2 py-1 transition-colors">
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