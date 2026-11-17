import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import Icon, { type IconName } from './Icon'

export type ToastTone = 'ok' | 'error' | 'warn' | 'info'

export interface ToastItem {
  id: number
  tone: ToastTone
  title?: string
  message: string
  duration?: number
}

interface ToastApi {
  push: (toast: Omit<ToastItem, 'id'>) => number
  success: (message: string, title?: string) => number
  error: (message: string, title?: string) => number
  warn: (message: string, title?: string) => number
  info: (message: string, title?: string) => number
  dismiss: (id: number) => void
  clear: () => void
}

const ToastContext = createContext<ToastApi | null>(null)

const TONE: Record<ToastTone, { icon: IconName; text: string; border: string; live: 'polite' | 'assertive' }> = {
  ok: { icon: 'check', text: 'text-state-ok', border: 'border-state-ok/40', live: 'polite' },
  error: { icon: 'alert', text: 'text-state-error', border: 'border-state-error/50', live: 'assertive' },
  warn: { icon: 'alert', text: 'text-state-warn', border: 'border-state-warn/40', live: 'polite' },
  info: { icon: 'info', text: 'text-brand-cyan', border: 'border-brand-cyan/40', live: 'polite' },
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const seq = useRef(0)
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>())

  useEffect(() => {
    const map = timers.current
    return () => {
      map.forEach((t) => clearTimeout(t))
      map.clear()
    }
  }, [])

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timers.current.delete(id)
    }
    setItems((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const push = useCallback(
    (toast: Omit<ToastItem, 'id'>) => {
      const id = ++seq.current
      const duration = toast.duration ?? (toast.tone === 'error' ? 8000 : 5000)
      setItems((prev) => [...prev, { ...toast, id }].slice(-5))
      timers.current.set(
        id,
        setTimeout(() => {
          timers.current.delete(id)
          setItems((prev) => prev.filter((t) => t.id !== id))
        }, duration)
      )
      return id
    },
    []
  )

  const api = useMemo<ToastApi>(
    () => ({
      push,
      success: (message, title) => push({ tone: 'ok', message, title }),
      error: (message, title) => push({ tone: 'error', message, title }),
      warn: (message, title) => push({ tone: 'warn', message, title }),
      info: (message, title) => push({ tone: 'info', message, title }),
      dismiss,
      clear: () => {
        timers.current.forEach((t) => clearTimeout(t))
        timers.current.clear()
        setItems([])
      },
    }),
    [push, dismiss]
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        className="fixed bottom-3 right-3 z-50 flex flex-col gap-2 w-[min(22rem,calc(100vw-1.5rem))]"
        role="region"
        aria-label="Notificaciones del sistema"
      >
        {items.map((item) => {
          const tone = TONE[item.tone]
          return (
            <div
              key={item.id}
              role="status"
              aria-live={tone.live}
              className={`animate-toast-in bg-base-panel border ${tone.border} shadow-lg shadow-black/40 p-2.5 flex items-start gap-2.5`}
            >
              <span className={`${tone.text} mt-px shrink-0`}>
                <Icon name={tone.icon} size={14} />
              </span>
              <div className="min-w-0 flex-1">
                {item.title && (
                  <div className={`font-condensed text-[10px] font-semibold tracking-[0.12em] uppercase ${tone.text}`}>
                    {item.title}
                  </div>
                )}
                <div className="text-[11px] leading-relaxed text-text-secondary break-words">
                  {item.message}
                </div>
              </div>
              <button
                type="button"
                onClick={() => dismiss(item.id)}
                aria-label="Cerrar notificación"
                className="text-text-muted hover:text-text-primary transition-colors shrink-0 p-0.5"
              >
                <Icon name="close" size={12} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast debe usarse dentro de <ToastProvider>')
  }
  return ctx
}
