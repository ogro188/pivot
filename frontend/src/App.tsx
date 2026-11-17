import { Routes, Route } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import NavBar from './components/NavBar'
import { useEffect, useRef } from 'react'
import { useStore } from './store'
import { fetchAssets, fetchSignals } from './api'
import { useToast, Skeleton, SkeletonCard } from './components/ui'
import { describeError } from './utils/errors'
import { esAltaConfianza } from './utils/signals'

const HubPage = lazy(() => import('./pages/HubPage'))
const ActivoPage = lazy(() => import('./pages/ActivoPage'))
const BacktestPage = lazy(() => import('./pages/BacktestPage'))
const EstrategiasPage = lazy(() => import('./pages/EstrategiasPage'))
const ConfigPage = lazy(() => import('./pages/ConfigPage'))

const SOUND_COOLDOWN_MS = 3000

function App() {
  const setWsConnected = useStore((s) => s.setWsConnected)
  const addSignal = useStore((s) => s.addSignal)
  const addLog = useStore((s) => s.addLog)
  const setAssetPrice = useStore((s) => s.setAssetPrice)
  const upsertCandle = useStore((s) => s.upsertCandle)
  const setDerivConnected = useStore((s) => s.setDerivConnected)
  const setDerivAssets = useStore((s) => s.setDerivAssets)
  const soundsEnabled = useStore((s) => s.soundsEnabled)
  const soundQueue = useStore((s) => s.soundQueue)
  const clearSoundQueue = useStore((s) => s.clearSoundQueue)
  const setPushNotificationsEnabled = useStore((s) => s.setPushNotificationsEnabled)
  const toast = useToast()

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const lastSoundTime = useRef(0)

  // Inicializar audio
  useEffect(() => {
    audioRef.current = new Audio('/sounds/alert.mp3')
    audioRef.current.volume = 0.3
  }, [])

  // Hidratar globalSignals desde la API al montar. El marcador en sessionStorage
  // solo se escribe si la hidratación termina bien, para que un fallo se reintente
  // en la próxima carga en lugar de dejar el panel de señales vacío en silencio.
  const hidrataRef = useRef(false)
  useEffect(() => {
    if (hidrataRef.current) return
    hidrataRef.current = true
    if (sessionStorage.getItem('signals_hydrated') === '1') return

    let cancelado = false

    fetchAssets()
      .then((assets: any[]) => {
        const symbols = assets.map((a: any) => a.simbolo).filter(Boolean)
        return Promise.all(symbols.map((s: string) => fetchSignals(s, 50).catch(() => [])))
      })
      .then((results) => {
        if (cancelado) return
        const all = results.flat().sort((a: any, b: any) => (a.ts || 0) - (b.ts || 0))
        const store = useStore.getState()
        for (const sig of all) {
          if (!store.globalSignals.find((s: any) => s.id === sig.id)) {
            store.addSignal(sig)
          }
        }
        sessionStorage.setItem('signals_hydrated', '1')
      })
      .catch((err) => {
        if (cancelado) return
        toast.error(describeError(err), 'Señales históricas')
      })

    return () => {
      cancelado = true
    }
  }, [toast])

  // Reproducir sonido si está habilitado y pasó el cooldown
  const playAlertSound = () => {
    const now = Date.now()
    if (now - lastSoundTime.current >= SOUND_COOLDOWN_MS && audioRef.current) {
      audioRef.current.play().catch(() => { /* autoplay bloqueado */ })
      lastSoundTime.current = now
    }
  }

  // Procesar cola de sonidos cuando se activan
  useEffect(() => {
    if (soundsEnabled && soundQueue.length > 0) {
      playAlertSound()
      clearSoundQueue()
    }
  }, [soundsEnabled, soundQueue, clearSoundQueue])

  // Sincronizar estado de notificaciones con permiso existente
  useEffect(() => {
    if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
      setPushNotificationsEnabled(true)
    }
  }, [setPushNotificationsEnabled])

  const isHighConfidence = (signal: any) => esAltaConfianza(signal)

  const sendPushNotification = (signal: any) => {
    if (!useStore.getState().pushNotificationsEnabled || !isHighConfidence(signal)) return
    if (Notification.permission !== 'granted') return
    try {
      new Notification(`PIVOT — ${signal.asset} ${signal.direccion === 1 ? 'LONG' : 'SHORT'}`, {
        body: `Confianza ${signal.confianza?.[0]}% @ ${signal.precio?.toFixed(5)}`,
        icon: '/pivot-icon.png',
        tag: `signal-${signal.id}`,
      })
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    let ws: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout>
    let backoff = 1000

    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      ws = new WebSocket(`${proto}//${window.location.host}/ws`)

      ws.onopen = () => {
        setWsConnected(true)
        backoff = 1000
      }

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type === 'signal' && msg.data) {
            addSignal(msg.data)
            // Sonido
            if (isHighConfidence(msg.data)) {
              if (useStore.getState().soundsEnabled) {
                playAlertSound()
              } else {
                // Acumular en cola
                useStore.setState((s: any) => ({ soundQueue: [msg.data, ...s.soundQueue].slice(0, 50) }))
              }
              // Push notification
              sendPushNotification(msg.data)
            }
          }
          if (msg.type === 'tick' && msg.asset && msg.price) {
            setAssetPrice(msg.asset, msg.price)
          }
          if (msg.type === 'candle' && msg.asset && msg.data) {
            upsertCandle(msg.asset, msg.timeframe || 'M15', msg.data)
          }
          if (msg.type === 'status') {
            setDerivConnected(!!msg.deriv_connected)
            if (msg.assets) setDerivAssets(msg.assets)
          }
          if (msg.type === 'consola' && msg.data) {
            addLog(msg.data)
          }
        } catch {
          // ignore malformed
        }
      }

      ws.onclose = () => {
        setWsConnected(false)
        reconnectTimer = setTimeout(connect, Math.min(backoff, 30000))
        backoff *= 2
      }

      ws.onerror = () => {
        ws?.close()
      }
    }

    connect()
    return () => {
      clearTimeout(reconnectTimer)
      ws?.close()
    }
  }, [setWsConnected, addSignal, addLog, setAssetPrice, upsertCandle, setDerivConnected, setDerivAssets])

  return (
    <div className="min-h-screen flex flex-col bg-base-bg text-text-primary">
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-base-panel focus:border focus:border-brand-cyan focus:text-text-primary focus:px-3 focus:py-2 focus:text-xs"
      >
        Saltar al contenido principal
      </a>
      <NavBar />
      <main id="contenido" className="flex-1 w-full max-w-[1680px] mx-auto p-3 sm:p-4">
        <Suspense
          fallback={
            <div className="space-y-4">
              <Skeleton className="h-8 w-48 rounded-sm" />
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
              </div>
            </div>
          }
        >
          <Routes>
            <Route path="/" element={<HubPage />} />
            <Route path="/activo/:simbolo" element={<ActivoPage />} />
            <Route path="/backtest" element={<BacktestPage />} />
            <Route path="/estrategias" element={<EstrategiasPage />} />
            <Route path="/config" element={<ConfigPage />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  )
}

export default App
