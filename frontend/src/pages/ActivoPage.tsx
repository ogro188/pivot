import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchSignals, fetchLogs, startAsset, stopAsset, fetchHistory, fetchAssets } from '../api'
import { useStore } from '../store'
import ChartHost from '../components/ChartHost'
import SignalCard from '../components/SignalCard'

export default function ActivoPage() {
  const { simbolo } = useParams<{ simbolo: string }>()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<'signals' | 'consola' | 'strategies'>('signals')
  const [tf, setTf] = useState('M15')
  const candles = useStore((s) => s.candles[`${simbolo}:${tf}`] || [])
  const setCandles = useStore((s) => s.setCandles)

  const { data: assets } = useQuery({ queryKey: ['assets'], queryFn: fetchAssets, refetchInterval: 5000 })
  const running = assets?.find((a: any) => a.simbolo === simbolo)?.running ?? false

  const { data: signals, refetch: refetchSignals } = useQuery({
    queryKey: ['signals', simbolo],
    queryFn: () => fetchSignals(simbolo!),
    refetchInterval: 5000,
    enabled: !!simbolo
  })
  const { data: logs } = useQuery({
    queryKey: ['logs', simbolo],
    queryFn: () => fetchLogs(simbolo!),
    refetchInterval: 5000,
    enabled: !!simbolo
  })

  useEffect(() => {
    if (!simbolo) return
    fetchHistory(simbolo, tf, 200).then((data) => {
      setCandles(simbolo, tf, data)
    }).catch(() => {
      setCandles(simbolo, tf, [])
    })
    const iv = setInterval(() => {
      fetchHistory(simbolo, tf, 200).then((data) => {
        setCandles(simbolo, tf, data)
      }).catch(() => {})
    }, 5000)
    return () => clearInterval(iv)
  }, [simbolo, tf, setCandles])

  const handleStart = async () => {
    try {
      await startAsset(simbolo!)
      queryClient.invalidateQueries({ queryKey: ['assets'] })
      refetchSignals()
    } catch {
      // endpoint no disponible o sin datos
    }
  }

  const handleStop = async () => {
    try {
      await stopAsset(simbolo!)
      queryClient.invalidateQueries({ queryKey: ['assets'] })
    } catch {
      // endpoint no disponible
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">{simbolo}</h1>
        <div className="flex gap-2">
          <button onClick={handleStart} className={`px-3 py-1 rounded text-sm ${running ? 'bg-gray-600 text-gray-300 cursor-default' : 'bg-green-600 hover:bg-green-700 text-white'}`}>
            {running ? 'Live' : 'Start'}
          </button>
          <button onClick={handleStop} disabled={!running} className={`px-3 py-1 rounded text-sm ${running ? 'bg-red-600 hover:bg-red-700 text-white' : 'bg-gray-700 text-gray-500 cursor-default'}`}>
            Stop
          </button>
        </div>
      </div>
      <div className="flex gap-2">
        {['M15', 'H1', 'H4', 'D1'].map((t) => (
          <button key={t} onClick={() => setTf(t)} className={`text-xs px-2 py-1 rounded ${tf === t ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'}`}>
            {t}
          </button>
        ))}
      </div>
      <ChartHost candles={candles} />
      <div className="flex gap-2 border-b border-gray-700 pb-2">
        {(['signals', 'consola', 'strategies'] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`px-3 py-1 rounded text-sm ${tab === t ? 'bg-gray-700 text-white' : 'text-gray-400'}`}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      {tab === 'signals' && (
        <div className="space-y-2">
          {signals?.map((s: any) => <SignalCard key={`${s.id}-${s.ts}`} signal={s} />)}
          {(!signals || signals.length === 0) && (
            <div className="text-gray-500 text-sm">No hay señales aún. Inicia el activo para generar el replay.</div>
          )}
        </div>
      )}
      {tab === 'consola' && (
        <div className="bg-gray-800 rounded-lg p-3 font-mono text-xs space-y-1 max-h-96 overflow-y-auto">
          {logs?.map((l: any, i: number) => (
            <div key={i} className={`${l.level === 'ERROR' ? 'text-red-400' : l.level === 'WARN' ? 'text-yellow-400' : 'text-gray-300'}`}>
              <span className="text-gray-500">{l.t}</span> <span className="font-bold">{l.cat}</span> {l.msg}
            </div>
          ))}
          {(!logs || logs.length === 0) && (
            <div className="text-gray-500">Sin logs.</div>
          )}
        </div>
      )}
      {tab === 'strategies' && (
        <div className="text-gray-400 text-sm">Configuración de estrategias por activo (próximamente)</div>
      )}
    </div>
  )
}
