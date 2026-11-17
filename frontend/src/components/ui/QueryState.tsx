import type { ReactNode } from 'react'
import ErrorState from './ErrorState'
import { SkeletonCard } from './Skeleton'

interface QueryStateProps {
  loading?: boolean
  error?: unknown
  onRetry?: () => void
  isEmpty?: boolean
  empty?: ReactNode
  skeleton?: ReactNode
  errorTitle?: string
  compact?: boolean
  children?: ReactNode
}

export default function QueryState({
  loading,
  error,
  onRetry,
  isEmpty,
  empty,
  skeleton,
  errorTitle = 'No se pudo cargar',
  compact,
  children,
}: QueryStateProps) {
  if (loading) return <>{skeleton ?? <SkeletonCard />}</>
  if (error) {
    return <ErrorState title={errorTitle} message={error} onRetry={onRetry} compact={compact} />
  }
  if (isEmpty) return <>{empty}</>
  return <>{children}</>
}
