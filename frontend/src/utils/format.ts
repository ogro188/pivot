const nf = (min: number, max: number) =>
  new Intl.NumberFormat('es-ES', { minimumFractionDigits: min, maximumFractionDigits: max })

export function fmtNum(value: unknown, decimals = 2): string {
  const n = toNumber(value)
  if (n === null) return '—'
  return nf(decimals, decimals).format(n)
}

export function fmtNumAuto(value: unknown, maxDecimals = 4): string {
  const n = toNumber(value)
  if (n === null) return '—'
  return nf(0, maxDecimals).format(n)
}

export function fmtPct(value: unknown, decimals = 1): string {
  const n = toNumber(value)
  if (n === null) return '—'
  return `${nf(decimals, decimals).format(n)}%`
}

export function fmtSigned(value: unknown, decimals = 2): string {
  const n = toNumber(value)
  if (n === null) return '—'
  const s = nf(decimals, decimals).format(Math.abs(n))
  return `${n > 0 ? '+' : n < 0 ? '−' : ''}${s}`
}

export function fmtMoney(value: unknown, decimals = 2): string {
  const n = toNumber(value)
  if (n === null) return '—'
  return `${nf(decimals, decimals).format(n)}`
}

export function fmtPrice(value: unknown, decimals = 5): string {
  const n = toNumber(value)
  if (n === null) return '—'
  return n.toFixed(decimals)
}

export function fmtCompact(value: unknown): string {
  const n = toNumber(value)
  if (n === null) return '—'
  const abs = Math.abs(n)
  if (abs >= 1e6) return `${nf(1, 1).format(n / 1e6)}M`
  if (abs >= 1e3) return `${nf(1, 1).format(n / 1e3)}k`
  return nf(0, 2).format(n)
}

export function toNumber(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value)
    return Number.isFinite(n) ? n : null
  }
  return null
}

const dtf = new Intl.DateTimeFormat('es-ES', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

const tf = new Intl.DateTimeFormat('es-ES', {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

const df = new Intl.DateTimeFormat('es-ES', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

export function toDate(value: unknown): Date | null {
  if (value === null || value === undefined || value === '') return null
  const d = value instanceof Date ? value : new Date(value as string | number)
  return Number.isNaN(d.getTime()) ? null : d
}

export function fmtDateTime(value: unknown): string {
  const d = toDate(value)
  if (!d) return '—'
  return dtf.format(d)
}

export function fmtTime(value: unknown): string {
  const d = toDate(value)
  if (!d) return '—'
  return tf.format(d)
}

export function fmtDate(value: unknown): string {
  const d = toDate(value)
  if (!d) return '—'
  return df.format(d)
}

export function fmtRelative(ts: number | string | undefined, now = Date.now()): string {
  const d = toDate(ts)
  if (!d) return '—'
  const diff = now - d.getTime()
  const abs = Math.abs(diff)
  const mins = Math.floor(abs / 60000)
  const future = diff < 0
  if (mins < 1) return future ? 'en instantes' : 'hace instantes'
  if (mins < 60) return future ? `en ${mins} min` : `hace ${mins} min`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return future ? `en ${hours} h` : `hace ${hours} h`
  const days = Math.floor(hours / 24)
  return future ? `en ${days} d` : `hace ${days} d`
}

export function fmtCountdown(ms: number): string {
  if (ms <= 0) return '00:00'
  const total = Math.floor(ms / 1000)
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  const p2 = (n: number) => n.toString().padStart(2, '0')
  if (days > 0) return `${days}d ${p2(hours)}:${p2(minutes)}`
  if (hours > 0) return `${p2(hours)}:${p2(minutes)}:${p2(seconds)}`
  return `${p2(minutes)}:${p2(seconds)}`
}
