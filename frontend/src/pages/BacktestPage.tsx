import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { fetchAssets, fetchStrategies, runBacktest, BacktestRequest } from '../api'
import ParamForm from '../components/ParamForm'

function errorDetail(err: any): string {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) return detail[0]?.msg || 'Error de validación'
  return err?.message || 'Error al ejecutar el backtest'
}

export default function BacktestPage() {
  const { data: assets } = useQuery({ queryKey: ['assets'], queryFn: fetchAssets })
  const { data: strategies } = useQuery({ queryKey: ['strategies'], queryFn: fetchStrategies })
  const [asset, setAsset] = useState('')
  const [strategy, setStrategy] = useState('')
  const [timeframe, setTimeframe] = useState('M15')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [params, setParams] = useState<Record<string, any>>({})

  const stratObj = strategies?.find((s: any) => s.nombre === strategy)

  const mutation = useMutation({
    mutationFn: runBacktest,
  })

  const result = mutation.data as any
  const loading = mutation.isPending
  const error = mutation.isError ? errorDetail(mutation.error) : null

  const handleSubmit = () => {
    const body: BacktestRequest = {
      estrategia: strategy,
      activo: asset,
      timeframe,
      fecha_inicio: desde.slice(0, 10),
      fecha_fin: hasta.slice(0, 10),
      capital_inicial: 10000,
      riesgo_por_operacion: 0.01,
      parametros: params,
    }
    mutation.mutate(body)
  }

  const equity = result?.equity || []
  const eqMin = equity.length ? Math.min(...equity.map((e: any) => e[1])) : 0
  const eqMax = equity.length ? Math.max(...equity.map((e: any) => e[1])) : 1
  const eqRange = eqMax - eqMin || 1

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Backtest</h1>
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Activo</label>
            <select className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm" value={asset} onChange={(e) => setAsset(e.target.value)}>
              <option value="">Seleccionar...</option>
              {assets?.map((a: any) => <option key={a.simbolo} value={a.simbolo}>{a.simbolo}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Estrategia</label>
            <select className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm" value={strategy} onChange={(e) => setStrategy(e.target.value)}>
              <option value="">Seleccionar...</option>
              {strategies?.map((s: any) => <option key={s.nombre} value={s.nombre}>{s.nombre}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Timeframe</label>
            <select className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm" value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
              {['M15', 'H1', 'H4', 'D1'].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Desde</label>
            <input type="datetime-local" className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm" value={desde} onChange={(e) => setDesde(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Hasta</label>
            <input type="datetime-local" className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm" value={hasta} onChange={(e) => setHasta(e.target.value)} />
          </div>
        </div>
        {stratObj ? (
          <ParamForm
            schema={stratObj.parametros}
            values={params}
            onChange={(k, v) => setParams((p) => ({ ...p, [k]: v }))}
            onSubmit={handleSubmit}
          />
        ) : (
          <button onClick={handleSubmit} disabled={loading} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm disabled:opacity-50">
            {loading ? 'Ejecutando...' : 'Ejecutar Backtest'}
          </button>
        )}
        {error && <div className="text-red-400 text-sm">{error}</div>}
      </div>
      {result && (
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h2 className="text-lg font-bold mb-3">Resultado: {result.status}</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-700 rounded p-3">
              <div className="text-xs text-gray-400">Operaciones</div>
              <div className="text-xl font-bold">{result.total_operaciones}</div>
            </div>
            <div className="bg-gray-700 rounded p-3">
              <div className="text-xs text-gray-400">Winrate</div>
              <div className="text-xl font-bold">{Number(result.winrate).toFixed(1)}%</div>
            </div>
            <div className="bg-gray-700 rounded p-3">
              <div className="text-xs text-gray-400">Profit Factor</div>
              <div className="text-xl font-bold">{result.profit_factor == null || !isFinite(result.profit_factor) ? 'N/A' : Number(result.profit_factor).toFixed(2)}</div>
            </div>
            <div className="bg-gray-700 rounded p-3">
              <div className="text-xs text-gray-400">Sharpe</div>
              <div className="text-xl font-bold">{result.sharpe_ratio == null ? 'N/A' : Number(result.sharpe_ratio).toFixed(2)}</div>
            </div>
            <div className="bg-gray-700 rounded p-3">
              <div className="text-xs text-gray-400">Retorno total</div>
              <div className="text-xl font-bold">{Number(result.retorno_total).toFixed(2)}%</div>
            </div>
            <div className="bg-gray-700 rounded p-3">
              <div className="text-xs text-gray-400">Drawdown máx</div>
              <div className="text-xl font-bold">{Number(result.drawdown_maximo).toFixed(2)}%</div>
            </div>
            <div className="bg-gray-700 rounded p-3">
              <div className="text-xs text-gray-400">Capital final</div>
              <div className="text-xl font-bold">{Number(result.capital_final ?? result.capital_inicial).toFixed(2)}</div>
            </div>
            <div className="bg-gray-700 rounded p-3">
              <div className="text-xs text-gray-400">Señales</div>
              <div className="text-xl font-bold">{result.n_senales ?? 0}</div>
            </div>
          </div>
          {equity.length > 0 && (
            <div className="mt-4">
              <div className="text-xs text-gray-400 mb-1">Equity curve (últimos puntos)</div>
              <div className="flex items-end gap-1 h-24">
                {equity.slice(-40).map(([ts, val]: [number, number], i: number) => {
                  const h = ((val - eqMin) / eqRange) * 100
                  return (
                    <div key={i} className="flex-1 bg-blue-600 rounded-t" style={{ height: `${Math.max(h, 2)}%` }} title={`${val.toFixed(2)}`} />
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
