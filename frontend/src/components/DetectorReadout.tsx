interface DetectorReadoutProps {
  activos: string[]
  clasificacion?: Record<string, 'A' | 'B' | 'C'>
}

const DETECTORES = ['D0', 'D1', 'D2', 'D3', 'D4', 'D5'] as const

const NOMBRES: Record<string, string> = {
  D0: 'ESTRUCTURA', D1: 'TENDENCIA', D2: 'SWEEP', D3: 'FVG', D4: 'ORDER BLOCK', D5: 'MSS',
}

export default function DetectorReadout({ activos, clasificacion = {} }: DetectorReadoutProps) {
  return (
    <div className="panel p-2.5 space-y-1.5">
      <div className="font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-2">Detectores</div>
      {DETECTORES.map((d) => {
        const activo = activos.includes(d)
        const clase = clasificacion[d]
        return (
          <div key={d} className="flex items-center gap-2">
            <svg width="12" height="12" viewBox="0 0 12 12" className="shrink-0">
              <polygon points="6,0 12,6 6,12 0,6" fill={activo ? '#37E0C4' : 'none'} stroke={activo ? '#37E0C4' : '#232936'} strokeWidth="1" />
            </svg>
            <span className={`font-mono text-[11px] ${activo ? 'text-text-primary' : 'text-text-muted'}`}>{d}</span>
            <span className={`font-condensed text-[11px] ${activo ? 'text-text-secondary' : 'text-text-muted/50'}`}>{NOMBRES[d]}</span>
            {clase && activo && (
              <span className="ml-auto font-mono text-[10px] px-1 border border-base-line text-text-secondary">{clase}</span>
            )}
          </div>
        )
      })}
    </div>
  )
}