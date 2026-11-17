import { Link, useLocation } from 'react-router-dom'
import { useStore } from '../store'
import { useCallback } from 'react'
import { Icon } from './ui'

const links = [
  { to: '/', label: 'HUB' },
  { to: '/backtest', label: 'BACKTEST' },
  { to: '/estrategias', label: 'ESTRATEGIAS' },
  { to: '/config', label: 'CONFIG' },
]

function RadarSweep({ active }: { active: boolean }) {
  return (
    <div className="relative w-3.5 h-3.5 shrink-0" aria-hidden="true">
      <div className="absolute inset-0 rounded-full border border-base-line" />
      {active && (
        <div
          className="absolute inset-0 rounded-full animate-radar-sweep"
          style={{
            background:
              'conic-gradient(from 0deg, transparent 0%, transparent 75%, rgba(55,224,196,0.9) 100%)',
          }}
        />
      )}
      <div
        className={`absolute inset-[3px] rounded-full ${active ? 'bg-brand-cyan/20' : 'bg-transparent'}`}
      />
    </div>
  )
}

function Toggle({
  pressed,
  onToggle,
  labelOn,
  labelOff,
  iconOn,
  iconOff,
}: {
  pressed: boolean
  onToggle: () => void
  labelOn: string
  labelOff: string
  iconOn: 'volume' | 'bell'
  iconOff: 'volumeOff' | 'bellOff'
}) {
  const text = pressed ? labelOn : labelOff
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={pressed}
      title={text}
      className={`w-7 h-7 flex items-center justify-center border transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand-cyan ${
        pressed
          ? 'border-brand-cyan/50 text-brand-cyan'
          : 'border-base-line text-text-muted hover:text-text-secondary'
      }`}
    >
      <Icon name={pressed ? iconOn : iconOff} size={14} />
      <span className="sr-only">{text}</span>
    </button>
  )
}

export default function NavBar() {
  const loc = useLocation()
  const wsConnected = useStore((s) => s.wsConnected)
  const derivConnected = useStore((s) => s.derivConnected)
  const soundsEnabled = useStore((s) => s.soundsEnabled)
  const setSoundsEnabled = useStore((s) => s.setSoundsEnabled)
  const pushNotificationsEnabled = useStore((s) => s.pushNotificationsEnabled)
  const setPushNotificationsEnabled = useStore((s) => s.setPushNotificationsEnabled)

  const requestNotificationPermission = useCallback(() => {
    if (typeof Notification === 'undefined') return
    if (Notification.permission === 'granted') {
      setPushNotificationsEnabled(true)
      return
    }
    if (Notification.permission === 'denied') return
    Notification.requestPermission().then((perm) => {
      if (perm === 'granted') setPushNotificationsEnabled(true)
    })
  }, [setPushNotificationsEnabled])

  return (
    <nav className="bg-base-panel border-b border-base-line px-3 h-11 flex items-center gap-1 font-condensed text-[13px] tracking-wide uppercase">
      <Link
        to="/"
        className="flex items-center gap-2 pr-3 mr-2 border-r border-base-line h-full shrink-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand-cyan"
        aria-label="PIVOT — ir al Hub"
      >
        <RadarSweep active={wsConnected} />
        <span className="font-mono font-semibold text-text-primary tracking-tight normal-case text-sm">
          PIVOT
        </span>
      </Link>

      <ul className="flex items-stretch min-w-0 overflow-x-auto">
        {links.map((l) => {
          const activo = loc.pathname === l.to
          return (
            <li key={l.to} className="shrink-0">
              <Link
                to={l.to}
                aria-current={activo ? 'page' : undefined}
                className={`px-3 h-11 flex items-center border-b-2 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand-cyan ${
                  activo
                    ? 'border-brand-cyan text-text-primary'
                    : 'border-transparent text-text-secondary hover:text-text-primary hover:border-base-line'
                }`}
              >
                {l.label}
              </Link>
            </li>
          )
        })}
      </ul>

      <div className="ml-auto flex items-center gap-2 sm:gap-3 shrink-0">
        <Toggle
          pressed={soundsEnabled}
          onToggle={() => setSoundsEnabled(!soundsEnabled)}
          labelOn="Desactivar sonidos"
          labelOff="Activar sonidos"
          iconOn="volume"
          iconOff="volumeOff"
        />
        <Toggle
          pressed={pushNotificationsEnabled}
          onToggle={requestNotificationPermission}
          labelOn="Notificaciones activas"
          labelOff="Activar notificaciones del navegador"
          iconOn="bell"
          iconOff="bellOff"
        />

        <div
          className="flex items-center gap-1.5 sm:pl-3 sm:border-l border-base-line h-full"
          title={wsConnected ? 'WebSocket conectado' : 'WebSocket desconectado'}
        >
          <div
            className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-brand-cyan animate-pulse-dot' : 'bg-base-line'}`}
            aria-hidden="true"
          />
          <span className="sr-only">{wsConnected ? 'Conectado' : 'Desconectado'}</span>
          <span className="hidden sm:inline font-mono text-[11px] text-text-secondary normal-case">
            {wsConnected ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>

        <div
          className="hidden sm:flex items-center gap-1.5 pl-3 border-l border-base-line h-full"
          title={derivConnected ? 'Conectado a Deriv API' : 'Sin conexión a Deriv API'}
        >
          <div
            className={`w-1.5 h-1.5 rounded-full ${derivConnected ? 'bg-brand-cyan animate-pulse-dot' : 'bg-base-line'}`}
            aria-hidden="true"
          />
          <span
            className={`font-mono text-[11px] normal-case ${derivConnected ? 'text-brand-cyan' : 'text-text-muted'}`}
          >
            DERIV {derivConnected ? 'ON' : 'OFF'}
          </span>
        </div>
      </div>
    </nav>
  )
}
