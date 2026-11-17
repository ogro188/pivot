export function describeError(err: unknown): string {
  if (err === null || err === undefined) return 'Error desconocido'
  if (typeof err === 'string' && err.trim() !== '') return err
  if (err instanceof Error && err.message) return err.message

  const e = err as {
    code?: string
    response?: { status?: number; statusText?: string; data?: { detail?: unknown; message?: string } }
    message?: string
  }

  const detail = e?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim() !== '') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string; message?: string }
    const msg = first?.msg || first?.message
    if (msg) return msg
  }

  const dataMessage = e?.response?.data?.message
  if (typeof dataMessage === 'string' && dataMessage.trim() !== '') return dataMessage

  if (e?.code === 'ERR_NETWORK' || e?.message === 'Network Error') {
    return 'No hay conexión con el servidor. Verificá que el backend esté corriendo en el puerto 8000.'
  }

  const status = e?.response?.status
  if (status) {
    const text = e.response?.statusText
    return text ? `El servidor respondió ${status} ${text}` : `El servidor respondió ${status}`
  }

  return e?.message || 'No se pudo completar la operación'
}

export function isNetworkError(err: unknown): boolean {
  const e = err as { code?: string; message?: string }
  return e?.code === 'ERR_NETWORK' || e?.message === 'Network Error'
}
