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
  const isLong = signal.direccion === 1
  const dirColor = isLong ? 'text-signal-long' : 'text-signal-short'
  const dirLabel = isLong ? 'LONG' : 'SHORT'

  if (isExpired) {
    return (
      <div className="panel p-2.5 opacity-60">
        <div className="flex justify-between items-center mb-1">
          <div className="flex items-center gap-2">
            <span className="font-condensed text-[11px] tracking-widest text-text-secondary uppercase">{signal.estrategia}</span>
            <span className="font-mono text-[10px] px-1 border border-base-line text-text-muted">{signal.etiqueta?.replace('PIVOT_', '') || '—'}</span>
          </div>
          <span className={`font-condensed text-[11px] tracking-widest ${dirColor}`}>{dirLabel}</span>
        </div>
        <div className="tabular text-sm text-text-primary">{signal.precio?.toFixed(5)}</div>
        <div className="font-condensed text-[10px] text-text-muted mt-1 normal-case">Expired</div>
        <div className="flex gap-2 mt-1.5">
          <span className="font-mono text-[10px] text-text-secondary">{signal.confianza[0]}%-{signal.confianza[1]}%</span>
        </div>
      </div>
    )
  }

  const minutes = Math.floor(remainingMs / 60000)
  const seconds = Math.floor((remainingMs % 60000) / 1000)

  return (
    <div className="panel p-2.5">
      <div className="flex justify-between items-center mb-1">
        <div className="flex items-center gap-2">
          <span className="font-condensed text-[11px] tracking-widest text-text-secondary uppercase">{signal.estrategia}</span>
          <span className="font-mono text-[10px] px-1 border border-base-line text-text-muted">{signal.etiqueta?.replace('PIVOT_', '') || '—'}</span>
        </div>
        <span className={`font-condensed text-[11px] tracking-widest ${dirColor}`}>{dirLabel}</span>
      </div>
      <div className="tabular text-sm text-text-primary">{signal.precio?.toFixed(5)}</div>
      <div className="font-condensed text-[11px] text-text-secondary mt-1 line-clamp-1 normal-case">{signal.narrativa}</div>
      <div className="flex justify-between items-center mt-1.5">
        <div className="flex gap-2">
          <span className="font-mono text-[10px] text-text-secondary">{signal.confianza[0]}%-{signal.confianza[1]}%</span>
        </div>
        <div className="font-mono text-[11px] text-brand-cyan tabular">
          {minutes.toString().padStart(2, '0')}:{seconds.toString().padStart(2, '0')}
        </div>
      </div>
    </div>
  )
}