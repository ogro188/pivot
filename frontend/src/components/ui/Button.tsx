import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import Icon, { type IconName } from './Icon'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'ok'
export type ButtonSize = 'sm' | 'md'

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    'bg-brand-cyan border-brand-cyan text-base-bg hover:bg-[#4BECD1] hover:border-[#4BECD1] font-semibold',
  secondary:
    'bg-base-panel border-base-edge text-text-secondary hover:bg-base-panel2 hover:text-text-primary',
  ghost:
    'bg-transparent border-transparent text-text-secondary hover:bg-base-panel2 hover:text-text-primary',
  danger:
    'bg-transparent border-state-error text-state-error hover:bg-state-error/10',
  ok: 'bg-transparent border-state-ok text-state-ok hover:bg-state-ok/10',
}

const SIZES: Record<ButtonSize, string> = {
  sm: 'h-7 px-2.5 text-[10px] gap-1',
  md: 'h-8 px-3.5 text-[11px] gap-1.5',
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  icon?: IconName
  iconRight?: IconName
  fullWidth?: boolean
  children?: ReactNode
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'secondary',
    size = 'md',
    loading = false,
    icon,
    iconRight,
    fullWidth = false,
    disabled,
    className = '',
    children,
    type = 'button',
    ...rest
  },
  ref
) {
  const iconSize = size === 'sm' ? 12 : 13
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={[
        'inline-flex items-center justify-center border font-condensed uppercase tracking-widest',
        'transition-colors select-none shrink-0',
        'disabled:opacity-45 disabled:cursor-not-allowed',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand-cyan',
        VARIANTS[variant],
        SIZES[size],
        fullWidth ? 'w-full' : '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      {...rest}
    >
      {loading ? <Icon name="spinner" size={iconSize} /> : icon ? <Icon name={icon} size={iconSize} /> : null}
      {children}
      {iconRight && !loading ? <Icon name={iconRight} size={iconSize} /> : null}
    </button>
  )
})

export default Button
