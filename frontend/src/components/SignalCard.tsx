import { SignalDTO } from '../store'

export default function SignalCard({ signal }: { signal: SignalDTO }) {
  const dirColor = signal.direccion === 1 ? 'text-green-400' : 'text-red-400'
  const dirLabel = signal.direccion === 1 ? 'CALL' : 'PUT'
  return (
    <div className="bg-gray-800 rounded-lg p-3 border border-gray-700 mb-2 hover:border-gray-500 transition-colors">
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs font-bold text-gray-400">{signal.estrategia}</span>
        <span className={`text-xs font-bold ${dirColor}`}>{dirLabel}</span>
      </div>
      <div className="text-sm font-mono">{signal.precio?.toFixed(5)}</div>
      <div className="text-xs text-gray-400 mt-1 line-clamp-2">{signal.narrativa}</div>
      <div className="flex gap-2 mt-2">
        <span className="text-xs bg-gray-700 px-2 py-0.5 rounded">{signal.etiqueta}</span>
        <span className="text-xs bg-gray-700 px-2 py-0.5 rounded">{signal.confianza[0]}%-{signal.confianza[1]}%</span>
      </div>
    </div>
  )
}
