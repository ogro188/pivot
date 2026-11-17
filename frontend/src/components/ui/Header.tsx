import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: ReactNode
  eyebrow?: ReactNode
  description?: ReactNode
  actions?: ReactNode
  className?: string
}

export function PageHeader({ title, eyebrow, description, actions, className = '' }: PageHeaderProps) {
  return (
    <header
      className={`flex flex-wrap items-start justify-between gap-3 pb-3 mb-4 border-b border-base-line ${className}`}
    >
      <div className="min-w-0">
        {eyebrow !== undefined && (
          <div className="font-condensed text-[10px] font-semibold tracking-[0.22em] uppercase text-text-muted mb-1.5">
            {eyebrow}
          </div>
        )}
        <h1 className="font-mono text-lg font-semibold text-text-primary leading-tight tracking-tight">
          {title}
        </h1>
        {description !== undefined && (
          <p className="mt-1.5 text-xs text-text-secondary max-w-2xl">{description}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

interface SectionTitleProps {
  children: ReactNode
  aside?: ReactNode
  className?: string
}

export function SectionTitle({ children, aside, className = '' }: SectionTitleProps) {
  return (
    <div className={`flex items-center justify-between gap-3 mb-2 ${className}`}>
      <h2 className="font-condensed text-[11px] font-semibold tracking-[0.16em] uppercase text-text-muted">
        {children}
      </h2>
      {aside && <div className="flex items-center gap-2">{aside}</div>}
    </div>
  )
}

interface FieldLabelProps {
  htmlFor?: string
  children: ReactNode
  hint?: ReactNode
}

export function FieldLabel({ htmlFor, children, hint }: FieldLabelProps) {
  return (
    <label
      htmlFor={htmlFor}
      className="flex items-baseline justify-between gap-2 mb-1 font-condensed text-[10px] font-semibold tracking-[0.14em] uppercase text-text-secondary"
    >
      <span>{children}</span>
      {hint && <span className="font-sans tracking-normal normal-case text-text-muted">{hint}</span>}
    </label>
  )
}
