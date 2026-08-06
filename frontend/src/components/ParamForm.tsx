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
        <div key={g} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h4 className="text-sm font-bold text-gray-300 mb-2">{g}</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {keys.map((k) => {
              const s = schema[k]
              const val = values[k] !== undefined ? values[k] : s.default
              return (
                <div key={k}>
                  <label className="block text-xs text-gray-400 mb-1">{s.label}</label>
                  {s.tipo === 'select' ? (
                    <select
                      className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm"
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
                      className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm"
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
      <button onClick={onSubmit} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm">
        Ejecutar Backtest
      </button>
    </div>
  )
}
