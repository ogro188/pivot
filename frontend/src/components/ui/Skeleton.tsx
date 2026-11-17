import type { CSSProperties } from 'react'

const BASE =
  'block bg-[linear-gradient(90deg,#141922_0%,#1F2634_50%,#141922_100%)] bg-[length:200%_100%] animate-skeleton-sweep'

interface SkeletonProps {
  className?: string
  style?: CSSProperties
}

export default function Skeleton({ className = '', style }: SkeletonProps) {
  return <span aria-hidden="true" className={`${BASE} ${className}`} style={style} />
}

export function SkeletonText({ lines = 3, className = '' }: { lines?: number; className?: string }) {
  return (
    <div className={`space-y-1.5 ${className}`} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className="h-2.5 rounded-sm"
          style={{ width: `${100 - (i % 3) * 18}%` }}
        />
      ))}
    </div>
  )
}

export function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={`bg-base-panel border border-base-line p-3 space-y-2.5 ${className}`} aria-hidden="true">
      <div className="flex items-center justify-between gap-3">
        <Skeleton className="h-3 w-20 rounded-sm" />
        <Skeleton className="h-3.5 w-12 rounded-sm" />
      </div>
      <Skeleton className="h-2 w-28 rounded-sm" />
      <Skeleton className="h-5 w-24 rounded-sm" />
      <Skeleton className="h-2 w-full rounded-sm" />
    </div>
  )
}

export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-px" aria-hidden="true">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-3 bg-base-panel px-3 py-2">
          {Array.from({ length: cols }).map((__, c) => (
            <Skeleton
              key={c}
              className="h-2.5 rounded-sm"
              style={{ width: c === 0 ? '22%' : `${12 + ((r + c) % 3) * 5}%` }}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

export function SkeletonChart({ height = 400 }: { height?: number }) {
  return (
    <div
      className="bg-base-panel border border-base-line flex items-end gap-1 p-3"
      style={{ height }}
      aria-hidden="true"
    >
      {Array.from({ length: 36 }).map((_, i) => (
        <Skeleton
          key={i}
          className="flex-1 rounded-t-sm"
          style={{ height: `${20 + ((i * 13) % 60)}%` }}
        />
      ))}
    </div>
  )
}
