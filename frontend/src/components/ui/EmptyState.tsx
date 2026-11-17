import type { ReactNode } from 'react'
import Icon, { type IconName } from './Icon'
import Button, { type ButtonProps } from './Button'

interface EmptyStateProps {
  icon?: IconName
  title: ReactNode
  description?: ReactNode
  action?: { label: string; onClick?: () => void; icon?: IconName } & Pick<
    ButtonProps,
    'variant' | 'size'
  >
  compact?: boolean
  className?: string
}

export default function EmptyState({
  icon = 'info',
  title,
  description,
  action,
  compact = false,
  className = '',
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center border border-dashed border-base-line bg-base-panel/40 ${
        compact ? 'py-5 px-3' : 'py-10 px-4'
      } ${className}`}
    >
      <div className="text-text-muted mb-2">
        <Icon name={icon} size={compact ? 16 : 20} />
      </div>
      <div className="font-condensed text-[11px] font-semibold tracking-[0.14em] uppercase text-text-secondary">
        {title}
      </div>
      {description && (
        <div className="mt-1 text-[11px] text-text-muted max-w-sm leading-relaxed">{description}</div>
      )}
      {action && (
        <Button
          variant={action.variant ?? 'secondary'}
          size={action.size ?? 'sm'}
          icon={action.icon}
          onClick={action.onClick}
          className="mt-3"
        >
          {action.label}
        </Button>
      )}
    </div>
  )
}
