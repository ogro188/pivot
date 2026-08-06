import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { fetchAssets, fetchStrategies, runBacktest, getBacktest } from '../api'
import ParamForm from '../components/ParamForm'

export default function BacktestPage() {
  const { data: assets } = useQuery({ queryKey: ['assets'], queryFn: fetchAssets })
  const { data: strategies } = useQuery({ queryKey: ['strategies'], queryFn: fetchStrategies })
  const [asset, setAsset] = useState('')
  const [strategy, setStrategy] = useState('')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [params, setParams] = useState<Record<string, any>>({})
  const [jobId, setJobId] = useState<string | null>(null)

  const stratObj = strategies?.find((s: any) => s.nombre === strategy)

  const mutation = useMutation({
    mutationFn: runBacktest,
    onSuccess: (data) => setJobId(data.job_id),
  })

  const { data: result } = useQuery({
    queryKey: ['backtest', jobId],
    queryFn: () => getBacktest(jobId!),
    enabled: !!jobId,
    refetchInterval: (data: any) => (data?.estado === 'running' ? 2000 : false),
  })

  const handleSubmit = () => {
    mutation.mutate({ asset, estrategia: strategy, desde, hasta, params })
  }

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
            <label className="block text-xs text-gray-400 mb-1">Desde</label>
            <input type="datetime-local" className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm" value={desde} onChange={(e) => setDesde(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Hasta</label>
            <input type="datetime-local" className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm" value={hasta} onChange={(e) => setHasta(e.target.value)} />
          </div>
        </div>
        {stratObj && (
          <ParamForm
            schema={stratObj.parametros}
            values={params}
            onChange={(k, v) => setParams((p) => ({ ...p, [k]: v }))}
            onSubmit={handleSubmit}
          />
        )}
        {!stratObj && (
          <button onClick={handleSubmit} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm">
            Ejecutar Backtest
          </button>
        )}
      </div>
      {result && (
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h2 className="text-lg font-bold mb-3">Resultado: {result.estado}</h2>
          {result.error && <div className="text-red-400 mb-3">{result.error}</div>}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-700 rounded p-3">
              <div className="text-xs text-gray-400">Señales</div>
              <div className="text-xl font-bold">{result.n_senales}</div>
            </div>
            <div className="bg-gray-700 rounded p-3">
              <div className="text-xs text-gray-400">Winrate</div>
              <div className="text-xl font-bold">{(result.winrate * 100).toFixed(1)}%</div>
            </div>
            <div className="bg-gray-700 rounded p-3">
              <div className="text-xs text-gray-400">Profit Factor</div>
              <div className="text-xl font-bold">{result.profit_factor?.toFixed(2) || 'N/A'}</div>
            </div>
            <div className="bg-gray-700 rounded p-3">
              <div className="text-xs text-gray-400">Sharpe</div>
              <div className="text-xl font-bold">{result.sharpe?.toFixed(2) || 'N/A'}</div>
            </div>
          </div>
          {result.equity && result.equity.length > 0 && (
            <div className="mt-4">
              <div className="text-xs text-gray-400 mb-1">Equity curve (últimos 20 puntos)</div>
              <div className="flex items-end gap-1 h-24">
                {result.equity.slice(-40).map(([ts, val]: [number, number], i: number) => {
                  const min = Math.min(...result.equity.map((e: any) => e[1]))
                  const max = Math.max(...result.equity.map((e: any) => e[1]))
                  const range = max - min || 1
                  const h = ((val - min) / range) * 100
                  return (
                    <div key={i} className="flex-1 bg-blue-600 rounded-t" style={{ height: `${Math.max(h, 5)}%` }} title={`${val.toFixed(1)}`} />
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
