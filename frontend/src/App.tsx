import { Routes, Route } from 'react-router-dom'
import HubPage from './pages/HubPage'
import ActivoPage from './pages/ActivoPage'
import BacktestPage from './pages/BacktestPage'
import EstrategiasPage from './pages/EstrategiasPage'
import ConfigPage from './pages/ConfigPage'
import NavBar from './components/NavBar'
import { useEffect, useRef } from 'react'
import { useStore } from './store'

const SOUND_COOLDOWN_MS = 3000

function App() {
  const setWsConnected = useStore((s) => s.setWsConnected)
  const addSignal = useStore((s) => s.addSignal)
  const addLog = useStore((s) => s.addLog)
  const setAssetPrice = useStore((s) => s.setAssetPrice)
  const soundsEnabled = useStore((s) => s.soundsEnabled)
  const soundQueue = useStore((s) => s.soundQueue)
  const clearSoundQueue = useStore((s) => s.clearSoundQueue)
  const pushNotificationsEnabled = useStore((s) => s.pushNotificationsEnabled)
  const setPushNotificationsEnabled = useStore((s) => s.setPushNotificationsEnabled)

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const lastSoundTime = useRef(0)

  // Inicializar audio
  useEffect(() => {
    audioRef.current = new Audio('/sounds/alert.mp3')
    audioRef.current.volume = 0.3
  }, [])

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

  // Solicitar permiso de notificaciones push al montar
  useEffect(() => {
    if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
      const denied = localStorage.getItem('notifications_denied')
      if (!denied) {
        // Mostrar toast/banner sutil - por simplicidad pedimos directo
        Notification.requestPermission().then((perm) => {
          if (perm === 'granted') {
            setPushNotificationsEnabled(true)
          } else if (perm === 'denied') {
            localStorage.setItem('notifications_denied', 'true')
          }
        })
      }
    } else if (Notification.permission === 'granted') {
      setPushNotificationsEnabled(true)
    }
  }, [setPushNotificationsEnabled])

  const isHighConfidence = (signal: any) => {
    const conv = signal.conviccion || ''
    const confMin = signal.confianza?.[0] || 0
    return conv === 'ALTA' || confMin > 70
  }

  const sendPushNotification = (signal: any) => {
    if (!pushNotificationsEnabled || !isHighConfidence(signal)) return
    if (Notification.permission !== 'granted') return
    try {
      new Notification(`PIVOT - ${signal.asset} ${signal.direccion === 1 ? 'LONG' : 'SHORT'}`, {
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
              if (soundsEnabled) {
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
  }, [setWsConnected, addSignal, addLog, setAssetPrice, soundsEnabled, pushNotificationsEnabled])

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <NavBar />
      <main className="p-4">
        <Routes>
          <Route path="/" element={<HubPage />} />
          <Route path="/activo/:simbolo" element={<ActivoPage />} />
          <Route path="/backtest" element={<BacktestPage />} />
          <Route path="/estrategias" element={<EstrategiasPage />} />
          <Route path="/config" element={<ConfigPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
