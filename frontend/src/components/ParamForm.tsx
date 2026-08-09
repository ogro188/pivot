import { useState } from 'react'

interface ParamSchema {
  tipo: string; default: any; min?: number; max?: number; label: string;
  grupo?: string; opciones?: string[]
}

export default function ParamForm({
  schema, values, onChange, onSubmit
}: {
  schema: Record<string, ParamSchema>; values: Record<string, any>;
  onChange: (k: string, v: any) => void; onSubmit: () => void
}) {
  const grupos: Record<string, string[]> = {}
  Object.entries(schema).forEach(([k, s]) => {
    const g = s.grupo || 'General'
    if (!grupos[g]) grupos[g] = []
    grupos[g].push(k)
  })

  return (
    <div className="space-y-4">
      {Object.entries(grupos).map(([g, keys]) => (
        <div key={g} className="panel p-3">
          <h4 className="font-condensed text-[11px] tracking-widest uppercase text-text-secondary mb-2">{g}</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {keys.map((k) => {
              const s = schema[k]
              const val = values[k] !== undefined ? values[k] : s.default
              return (
                <div key={k}>
                  <label className="block font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-1">{s.label}</label>
                  {s.tipo === 'select' ? (
                    <select
                      className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-sm text-text-primary"
                      value={val}
                      onChange={(e) => onChange(k, e.target.value)}
                    >
                      {s.opciones?.map((o) => <option key={o}>{o}</option>)}
                    </select>
                  ) : s.tipo === 'bool' ? (
                    <input
                      type="checkbox"
                      checked={val}
                      onChange={(e) => onChange(k, e.target.checked)}
                    />
                  ) : (
                    <input
                      type={s.tipo === 'int' || s.tipo === 'float' ? 'number' : 'text'}
                      min={s.min} max={s.max}
                      className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-sm text-text-primary tabular"
                      value={val}
                      onChange={(e) => onChange(k, s.tipo === 'int' ? parseInt(e.target.value) : s.tipo === 'float' ? parseFloat(e.target.value) : e.target.value)}
                    />
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}
      <button onClick={onSubmit} className="border border-brand-cyan/50 text-brand-cyan hover:bg-brand-cyan/10 px-4 py-1.5 font-condensed text-[11px] tracking-widest uppercase transition-colors">
        Ejecutar Backtest
      </button>
    </div>
  )
}