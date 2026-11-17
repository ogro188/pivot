import type { ReactNode } from 'react'
import Icon from './Icon'
import Button from './Button'
import { describeError } from '../../utils/errors'

interface ErrorStateProps {
  title?: ReactNode
  message?: unknown
  onRetry?: () => void
  retryLabel?: string
  compact?: boolean
  className?: string
}

export default function ErrorState({
  title = 'No se pudo cargar',
  message,
  onRetry,
  retryLabel = 'Reintentar',
  compact = false,
  className = '',
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={`flex items-start gap-2.5 border border-state-error/40 bg-state-error/[0.07] ${
        compact ? 'p-2.5' : 'p-3'
      } ${className}`}
    >
      <span className="text-state-error mt-px shrink-0">
        <Icon name="alert" size={compact ? 13 : 15} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="font-condensed text-[11px] font-semibold tracking-[0.12em] uppercase text-state-error">
          {title}
        </div>
        <div className="mt-0.5 text-[11px] leading-relaxed text-text-secondary break-words">
          {describeError(message)}
        </div>
      </div>
      {onRetry && (
        <Button variant="secondary" size="sm" icon="refresh" onClick={onRetry}>
          {retryLabel}
        </Button>
      )}
    </div>
  )
}
