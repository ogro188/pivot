import type { ReactNode } from 'react'

export type BadgeTone = 'neutral' | 'brand' | 'long' | 'short' | 'ok' | 'warn' | 'error' | 'muted'

const TONES: Record<BadgeTone, string> = {
  neutral: 'border-base-edge text-text-secondary bg-base-panel2',
  brand: 'border-brand-cyan/50 text-brand-cyan bg-brand-cyan/10',
  long: 'border-signal-long/50 text-signal-long bg-signal-long/10',
  short: 'border-signal-short/50 text-signal-short bg-signal-short/10',
  ok: 'border-state-ok/50 text-state-ok bg-state-ok/10',
  warn: 'border-state-warn/50 text-state-warn bg-state-warn/10',
  error: 'border-state-error/50 text-state-error bg-state-error/10',
  muted: 'border-base-line text-text-muted bg-base-panel2',
}

interface BadgeProps {
  tone?: BadgeTone
  children: ReactNode
  className?: string
  title?: string
}

export default function Badge({ tone = 'neutral', children, className = '', title }: BadgeProps) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 border px-1.5 py-[3px] font-condensed text-[10px] font-semibold tracking-[0.12em] uppercase leading-none ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  )
}
