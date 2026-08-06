import { Routes, Route } from 'react-router-dom'
import HubPage from './pages/HubPage'
import ActivoPage from './pages/ActivoPage'
import BacktestPage from './pages/BacktestPage'
import EstrategiasPage from './pages/EstrategiasPage'
import ConfigPage from './pages/ConfigPage'
import NavBar from './components/NavBar'
import { useEffect } from 'react'
import { useStore } from './store'

function App() {
  const setWsConnected = useStore((s) => s.setWsConnected)
  const addSignal = useStore((s) => s.addSignal)
  const addLog = useStore((s) => s.addLog)
  const setAssetPrice = useStore((s) => s.setAssetPrice)

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
          }
          if (msg.type === 'tick' && msg.data) {
            setAssetPrice(msg.asset, msg.data.price)
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
  }, [setWsConnected, addSignal, addLog, setAssetPrice])

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
