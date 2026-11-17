import { Panel, Badge } from './ui'

interface DetectorReadoutProps {
  activos: string[]
  clasificacion?: Record<string, 'A' | 'B' | 'C'>
}

const DETECTORES = ['D0', 'D1', 'D2', 'D3', 'D4', 'D5'] as const

const NOMBRES: Record<string, string> = {
  D0: 'ESTRUCTURA',
  D1: 'RUPTURA',
  D2: 'SWEEP',
  D3: 'FVG',
  D4: 'ORDER BLOCK',
  D5: 'MSS',
}

export default function DetectorReadout({
  activos,
  clasificacion = {},
}: DetectorReadoutProps) {
  const total = activos.length

  return (
    <Panel
      title="Detectores"
      subtitle={total === 0 ? 'Ninguno activo en la señal' : `${total} confluente${total === 1 ? '' : 's'}`}
    >
      <ul className="space-y-1.5">
        {DETECTORES.map((d) => {
          const activo = activos.includes(d)
          const clase = clasificacion[d]
          return (
            <li key={d} className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className={`w-2.5 h-2.5 shrink-0 rotate-45 border ${
                  activo ? 'bg-state-ok border-state-ok' : 'bg-transparent border-base-line'
                }`}
              />
              <span
                className={`font-mono text-[11px] tabular ${activo ? 'text-text-primary' : 'text-text-muted'}`}
              >
                {d}
              </span>
              <span
                className={`font-condensed text-[11px] tracking-wide ${
                  activo ? 'text-text-secondary' : 'text-text-muted'
                }`}
              >
                {NOMBRES[d]}
              </span>
              {clase && activo && (
                <span className="ml-auto">
                  <Badge tone="neutral">{clase}</Badge>
                </span>
              )}
              {activo && <span className="sr-only">activo</span>}
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}
