import { SignalDTO } from '../store'

interface SignalCountdownProps {
  signal: SignalDTO
  onExpire?: () => void
}

export default function SignalCountdown({ signal, onExpire }: SignalCountdownProps) {
  const timeframe = signal.timeframe || 'M15'
  const minutesPerCandle = timeframe === 'M15' ? 15 : timeframe === 'H1' ? 60 : timeframe === 'H4' ? 240 : 1440
  const expirationMs = (signal.ts || 0) + signal.expiracion_velas * minutesPerCandle * 60 * 1000
  const now = Date.now()
  const remainingMs = expirationMs - now
  const isExpired = remainingMs <= 0

  if (isExpired) {
    return (
      <div className="bg-gray-800 rounded-lg p-3 border border-gray-700 opacity-60">
        <div className="flex justify-between items-center mb-1">
          <span className="text-xs font-bold text-gray-400">{signal.estrategia}</span>
          <span className={`text-xs font-bold ${signal.direccion === 1 ? 'text-green-400' : 'text-red-400'}`}>
            {signal.direccion === 1 ? 'LONG' : 'SHORT'}
          </span>
        </div>
        <div className="text-sm font-mono">{signal.precio?.toFixed(5)}</div>
        <div className="text-xs text-gray-500 mt-1">Expirada</div>
        <div className="flex gap-2 mt-2">
          <span className="text-xs bg-gray-700 px-2 py-0.5 rounded">{signal.etiqueta}</span>
          <span className="text-xs text-gray-500">{signal.confianza[0]}%-{signal.confianza[1]}%</span>
        </div>
      </div>
    )
  }

  const minutes = Math.floor(remainingMs / 60000)
  const seconds = Math.floor((remainingMs % 60000) / 1000)

  return (
    <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs font-bold text-gray-400">{signal.estrategia}</span>
        <span className={`text-xs font-bold ${signal.direccion === 1 ? 'text-green-400' : 'text-red-400'}`}>
          {signal.direccion === 1 ? 'LONG' : 'SHORT'}
        </span>
      </div>
      <div className="text-sm font-mono">{signal.precio?.toFixed(5)}</div>
      <div className="text-xs text-gray-400 mt-1 line-clamp-1">{signal.narrativa}</div>
      <div className="flex justify-between items-center mt-2">
        <div className="flex gap-2">
          <span className="text-xs bg-gray-700 px-2 py-0.5 rounded">{signal.etiqueta}</span>
          <span className="text-xs bg-gray-700 px-2 py-0.5 rounded">{signal.confianza[0]}%-{signal.confianza[1]}%</span>
        </div>
        <div className="text-xs font-mono text-yellow-400 tabular-nums">
          {minutes.toString().padStart(2, '0')}:{seconds.toString().padStart(2, '0')}
        </div>
      </div>
    </div>
  )
}