import type { SignalDTO } from '../store'

const RAICES = ['D0', 'D1', 'D2', 'D3', 'D4', 'D5'] as const

export type DetectorId = (typeof RAICES)[number]

export function normalizarDetectores(detectores: unknown): DetectorId[] {
  if (!Array.isArray(detectores)) return []
  const set = new Set<string>()
  for (const item of detectores) {
    if (item === null || item === undefined) continue
    for (const parte of String(item).split(',')) {
      const m = /^D[0-5]/.exec(parte.trim())
      if (m && RAICES.includes(m[0] as DetectorId)) set.add(m[0])
    }
  }
  return RAICES.filter((r) => set.has(r))
}

export function minutosPorVela(timeframe?: string): number {
  switch (timeframe || 'M15') {
    case 'M15':
      return 15
    case 'H1':
      return 60
    case 'H4':
      return 240
    case 'D1':
      return 1440
    default:
      return 15
  }
}

export function expiraEn(signal: { ts?: number; expiracion_velas?: number; timeframe?: string }): number {
  return (signal.ts || 0) + (signal.expiracion_velas || 0) * minutosPorVela(signal.timeframe) * 60 * 1000
}

export function estaExpirada(signal: SignalDTO, now = Date.now()): boolean {
  return expiraEn(signal) <= now
}

export function esDireccionValida(signal: SignalDTO): boolean {
  return signal.direccion === 1 || signal.direccion === -1
}

export function esAltaConfianza(signal: SignalDTO): boolean {
  if (String(signal.conviccion || '').toUpperCase() === 'ALTA') return true
  return (signal.confianza?.[0] ?? 0) > 70
}

export function nivelDeConfianza(signal: SignalDTO): 'ALTA' | 'MEDIA' | 'BAJA' {
  if (esAltaConfianza(signal)) return 'ALTA'
  const conv = String(signal.conviccion || '').toUpperCase()
  if (conv === 'MEDIA' || conv === 'BAJA') return conv
  return (signal.confianza?.[0] ?? 0) >= 60 ? 'MEDIA' : 'BAJA'
}
