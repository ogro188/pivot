import { SignalDTO } from '../store'

export default function SignalCard({ signal }: { signal: SignalDTO }) {
  const isLong = signal.direccion === 1
  const dirColor = isLong ? 'text-signal-long' : 'text-signal-short'
  const dirLabel = isLong ? 'LONG' : 'SHORT'
  return (
    <div className="panel p-2.5 mb-1.5 hover:border-base-line transition-colors">
      <div className="flex justify-between items-center mb-1">
        <div className="flex items-center gap-2">
          <span className="font-condensed text-[11px] tracking-widest text-text-secondary uppercase">{signal.estrategia}</span>
          <span className="font-mono text-[10px] px-1 border border-base-line text-text-muted">{signal.etiqueta?.replace('PIVOT_', '') || '—'}</span>
        </div>
        <span className={`font-condensed text-[11px] tracking-widest ${dirColor}`}>{dirLabel}</span>
      </div>
      <div className="tabular text-sm text-text-primary">{signal.precio?.toFixed(5)}</div>
      <div className="font-condensed text-[11px] text-text-muted mt-1 line-clamp-2 normal-case">{signal.narrativa}</div>
      <div className="flex gap-2 mt-1.5">
        <span className="font-mono text-[10px] text-text-secondary">{signal.confianza[0]}%-{signal.confianza[1]}%</span>
      </div>
    </div>
  )
}