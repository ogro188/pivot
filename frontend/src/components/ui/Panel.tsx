import type { ReactNode } from 'react'

interface PanelProps {
  title?: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
  padded?: boolean
  as?: 'section' | 'div' | 'article'
}

export default function Panel({
  title,
  subtitle,
  actions,
  children,
  className = '',
  bodyClassName = '',
  padded = true,
  as: Tag = 'section',
}: PanelProps) {
  const hasHeader = title !== undefined || actions !== undefined
  return (
    <Tag className={`bg-base-panel border border-base-line ${className}`}>
      {hasHeader && (
        <header className="flex items-center justify-between gap-3 border-b border-base-line px-3 py-2">
          <div className="min-w-0">
            {title !== undefined && (
              <h2 className="font-condensed text-[11px] font-semibold tracking-[0.14em] uppercase text-text-secondary truncate">
                {title}
              </h2>
            )}
            {subtitle !== undefined && (
              <div className="mt-0.5 text-[11px] text-text-muted truncate">{subtitle}</div>
            )}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </header>
      )}
      <div className={padded ? `p-3 ${bodyClassName}` : bodyClassName}>{children}</div>
    </Tag>
  )
}
