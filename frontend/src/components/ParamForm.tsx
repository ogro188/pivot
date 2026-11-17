import { FieldLabel, Button, Panel } from './ui'

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

interface ParamFormProps {
  schema: Record<string, ParamSchema>
  values: Record<string, any>
  onChange: (k: string, v: any) => void
  onSubmit: () => void
  loading?: boolean
  hideSubmit?: boolean
}

const INPUT =
  'w-full bg-base-panel2 border border-base-line px-2 h-8 text-sm text-text-primary focus:border-base-edge focus:outline-none'

export default function ParamForm({
  schema,
  values,
  onChange,
  onSubmit,
  loading,
  hideSubmit = false,
}: ParamFormProps) {
  const grupos: Record<string, string[]> = {}
  Object.entries(schema).forEach(([k, s]) => {
    const g = s.grupo || 'General'
    if (!grupos[g]) grupos[g] = []
    grupos[g].push(k)
  })

  return (
    <div className="space-y-3">
      {Object.entries(grupos).map(([g, keys]) => (
        <Panel key={g} title={g}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {keys.map((k) => {
              const s = schema[k]
              const val = values[k] !== undefined ? values[k] : s.default
              const hint = [s.min !== undefined ? `mín ${s.min}` : '', s.max !== undefined ? `máx ${s.max}` : '']
                .filter(Boolean)
                .join(' · ')

              if (s.tipo === 'bool') {
                return (
                  <label
                    key={k}
                    htmlFor={`param-${k}`}
                    className="flex items-center justify-between gap-3 border border-base-line bg-base-panel2 px-2.5 h-8 cursor-pointer hover:border-base-edge transition-colors"
                  >
                    <span className="font-condensed text-[10px] font-semibold tracking-[0.14em] uppercase text-text-secondary truncate">
                      {s.label || s.descripcion || k}
                    </span>
                    <input
                      id={`param-${k}`}
                      type="checkbox"
                      className="w-4 h-4 accent-brand-cyan shrink-0"
                      checked={!!val}
                      onChange={(e) => onChange(k, e.target.checked)}
                    />
                  </label>
                )
              }

              return (
                <div key={k}>
                  <FieldLabel htmlFor={`param-${k}`} hint={hint || undefined}>
                    {s.label || s.descripcion || k}
                  </FieldLabel>
                  {s.tipo === 'select' ? (
                    <select
                      id={`param-${k}`}
                      className={INPUT}
                      value={val}
                      onChange={(e) => onChange(k, e.target.value)}
                    >
                      {s.opciones?.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      id={`param-${k}`}
                      type={s.tipo === 'int' || s.tipo === 'float' ? 'number' : 'text'}
                      min={s.min}
                      max={s.max}
                      step={s.tipo === 'float' ? 'any' : 1}
                      className={`${INPUT} tabular`}
                      value={val ?? ''}
                      onChange={(e) =>
                        onChange(
                          k,
                          s.tipo === 'int'
                            ? parseInt(e.target.value, 10)
                            : s.tipo === 'float'
                              ? parseFloat(e.target.value)
                              : e.target.value
                        )
                      }
                    />
                  )}
                </div>
              )
            })}
          </div>
        </Panel>
      ))}

      {!hideSubmit && (
        <div>
          <Button variant="primary" icon="activity" onClick={onSubmit} loading={loading}>
            Ejecutar backtest
          </Button>
        </div>
      )}
    </div>
  )
}
