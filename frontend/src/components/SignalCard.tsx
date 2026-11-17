import { memo } from 'react'
import { SignalDTO } from '../store'
import { SIGNAL_LONG, SIGNAL_SHORT } from '../theme'
import Badge from './ui/Badge'
import { normalizarDetectores, expiraEn, nivelDeConfianza, esAltaConfianza } from '../utils/signals'
import { fmtCountdown, fmtPrice } from '../utils/format'
import { useNowTick } from '../hooks/useNowTick'

interface SignalCardProps {
  signal: SignalDTO
  variant?: 'active' | 'expired' | 'compact'
  showCountdown?: boolean
}

const NOMBRES_DETECTORES: Record<string, string> = {
  D0: 'Estructura',
  D1: 'Ruptura',
  D2: 'Sweep',
  D3: 'FVG',
  D4: 'Order Block',
  D5: 'MSS',
}

function SignalCardBase({ signal, variant = 'active', showCountdown = true }: SignalCardProps) {
  const now = useNowTick()
  const isLong = signal.direccion === 1
  const dirColor = isLong ? 'text-signal-long' : 'text-signal-short'
  const dirLabel = isLong ? 'CALL · LONG' : 'PUT · SHORT'
  const rail = isLong ? SIGNAL_LONG : SIGNAL_SHORT
  const detectores = normalizarDetectores(signal.detectores)
  const nivel = nivelDeConfianza(signal)
  const expiracion = expiraEn(signal)
  const restante = expiracion - now
  const expirada = restante <= 0
  const decimales = signal.precio && signal.precio > 100 ? 2 : 5
  const esDatosPrueba = signal.datos_prueba === true

  return (
    <article
      className="bg-base-panel border border-base-line hover:border-base-edge transition-colors"
      style={{ borderLeft: `2px solid ${rail}` }}
    >
      {esDatosPrueba && (
        <div className="font-mono text-[9px] tracking-wider text-state-warn border-b border-state-warn/30 bg-state-warn/[0.07] px-2.5 py-1 uppercase">
          Datos de prueba — no es precio de mercado
        </div>
      )}

      <div className="px-2.5 py-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-1.5 flex-wrap min-w-0">
            <span className="font-condensed text-[10px] font-semibold tracking-[0.14em] uppercase text-text-secondary">
              {signal.estrategia}
            </span>
            {signal.etiqueta && (
              <Badge tone="muted">{signal.etiqueta.replace('PIVOT_', '')}</Badge>
            )}
            {esAltaConfianza(signal) && <Badge tone="brand">{nivel}</Badge>}
          </div>
          <span className={`font-condensed text-[11px] font-bold tracking-[0.1em] shrink-0 ${dirColor}`}>
            {dirLabel}
          </span>
        </div>

        <div className="flex items-baseline gap-2 mt-1.5">
          <span className="tabular font-mono text-xl text-text-primary leading-none">
            {fmtPrice(signal.precio, decimales)}
          </span>
          <span className="font-mono text-[10px] text-text-muted">{signal.asset}</span>
          {signal.timeframe && (
            <span className="font-mono text-[10px] text-text-muted">· {signal.timeframe}</span>
          )}
        </div>

        {variant !== 'compact' && signal.narrativa && (
          <p className="text-[11px] leading-snug text-text-secondary mt-1.5 line-clamp-2">
            {signal.narrativa}
          </p>
        )}

        {detectores.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {detectores.map((d) => (
              <span
                key={d}
                title={NOMBRES_DETECTORES[d]}
                className="font-mono text-[9px] border border-base-line bg-base-panel2 px-1 py-px text-text-secondary"
              >
                {d}
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between gap-2 mt-2 pt-2 border-t border-base-line">
          <span className="font-mono text-[10px] tabular text-text-secondary">
            {signal.confianza?.[0]}–{signal.confianza?.[1]}%
          </span>

          {variant !== 'expired' && showCountdown && (
            <span
              className={`font-mono text-[11px] tabular ${
                restante < 60000 ? 'text-state-warn' : 'text-brand-cyan'
              }`}
              title={`Expira ${new Date(expiracion).toLocaleString('es-ES')}`}
            >
              {fmtCountdown(restante)}
            </span>
          )}

          {variant === 'expired' && (
            <span className="font-condensed text-[10px] tracking-[0.14em] uppercase text-text-muted">
              Expirada
            </span>
          )}
        </div>
      </div>
    </article>
  )
}

const SignalCard = memo(SignalCardBase)
export default SignalCard
