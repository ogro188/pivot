import { SignalDTO } from '../store'

export function exportSignalsToCsv(signals: SignalDTO[], filename?: string) {
  const headers = [
    'timestamp',
    'asset',
    'estrategia',
    'etiqueta',
    'direccion',
    'precio',
    'confianza_min',
    'confianza_max',
    'expiracion_velas',
    'narrativa',
    'estado',
  ]

  const rows = signals.map((s) => [
    new Date(s.ts).toISOString(),
    s.asset,
    s.estrategia,
    s.etiqueta,
    s.direccion === 1 ? 'LONG' : 'SHORT',
    s.precio?.toFixed(5) || '',
    s.confianza[0] || '',
    s.confianza[1] || '',
    s.expiracion_velas || '',
    `"${(s.narrativa || '').replace(/"/g, '""')}"`,
    s.estado || '',
  ])

  const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename || `pivot_signals_${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}