import { useMemo, useState, type ReactNode } from 'react'
import Icon from './Icon'

export interface Column<T> {
  key: string
  header: ReactNode
  align?: 'left' | 'right' | 'center'
  width?: string
  sortable?: boolean
  sortValue?: (row: T) => string | number
  render?: (row: T) => ReactNode
  numeric?: boolean
  headerClassName?: string
  cellClassName?: string
}

export interface SortState {
  key: string
  dir: 'asc' | 'desc'
}

interface DataTableProps<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string
  initialSort?: SortState
  empty?: ReactNode
  caption?: string
  dense?: boolean
  maxHeight?: number | string
  onRowClick?: (row: T) => void
  isRowSelected?: (row: T) => boolean
  className?: string
}

const ALIGN: Record<string, string> = {
  left: 'text-left',
  right: 'text-right',
  center: 'text-center',
}

export default function DataTable<T>({
  columns,
  rows,
  rowKey,
  initialSort,
  empty,
  caption,
  dense = false,
  maxHeight,
  onRowClick,
  isRowSelected,
  className = '',
}: DataTableProps<T>) {
  const [sort, setSort] = useState<SortState | null>(initialSort ?? null)

  const sorted = useMemo(() => {
    if (!sort) return rows
    const col = columns.find((c) => c.key === sort.key)
    if (!col?.sortValue) return rows
    const value = col.sortValue
    const mul = sort.dir === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      const x = value(a)
      const y = value(b)
      if (typeof x === 'number' && typeof y === 'number') return (x - y) * mul
      return String(x).localeCompare(String(y), 'es') * mul
    })
  }, [rows, sort, columns])

  const toggleSort = (col: Column<T>) => {
    if (!col.sortable) return
    setSort((prev) =>
      prev && prev.key === col.key
        ? prev.dir === 'asc'
          ? { key: col.key, dir: 'desc' }
          : null
        : { key: col.key, dir: 'asc' }
    )
  }

  if (rows.length === 0 && empty) {
    return <div className={className}>{empty}</div>
  }

  const pad = dense ? 'px-2 py-1' : 'px-2.5 py-1.5'

  return (
    <div
      className={`overflow-auto border border-base-line bg-base-panel ${className}`}
      style={maxHeight ? { maxHeight } : undefined}
    >
      <table className="w-full border-collapse text-[11px]">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((col) => {
              const isSorted = sort?.key === col.key
              const ariaSort = !col.sortable
                ? undefined
                : isSorted
                  ? sort!.dir === 'asc'
                    ? 'ascending'
                    : 'descending'
                  : 'none'
              return (
                <th
                  key={col.key}
                  scope="col"
                  aria-sort={ariaSort}
                  style={col.width ? { width: col.width } : undefined}
                  className={[
                    'sticky top-0 z-10 bg-base-panel2 border-b border-base-line',
                    'font-condensed text-[10px] font-semibold tracking-[0.12em] uppercase text-text-muted',
                    pad,
                    col.numeric ? 'text-right' : ALIGN[col.align ?? 'left'],
                    col.headerClassName ?? '',
                  ].join(' ')}
                >
                  {col.sortable ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(col)}
                      className={`inline-flex items-center gap-1 hover:text-text-primary transition-colors ${
                        isSorted ? 'text-brand-cyan' : ''
                      }`}
                    >
                      {col.header}
                      <Icon
                        name={isSorted && sort!.dir === 'desc' ? 'arrowDown' : 'arrowUp'}
                        size={10}
                        className={isSorted ? 'opacity-100' : 'opacity-30'}
                      />
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const key = rowKey(row)
            const selected = isRowSelected?.(row) ?? false
            return (
              <tr
                key={key}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={[
                  'border-b border-base-line/60 transition-colors',
                  onRowClick ? 'cursor-pointer' : '',
                  selected ? 'bg-brand-cyan/[0.07]' : '',
                  selected ? '' : 'hover:bg-base-panel2',
                ].join(' ')}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={[
                      pad,
                      col.numeric ? 'tabular text-right text-text-primary' : 'text-text-secondary',
                      col.align ? ALIGN[col.align] : '',
                      col.cellClassName ?? '',
                    ].join(' ')}
                  >
                    {col.render ? col.render(row) : (row as Record<string, ReactNode>)[col.key]}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
