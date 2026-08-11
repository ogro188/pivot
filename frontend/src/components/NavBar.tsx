import { Link, useLocation } from 'react-router-dom'
import { useStore } from '../store'

const links = [
  { to: '/', label: 'HUB' },
  { to: '/backtest', label: 'BACKTEST' },
  { to: '/estrategias', label: 'ESTRATEGIAS' },
  { to: '/config', label: 'CONFIG' },
]

function RadarSweep({ active }: { active: boolean }) {
  return (
    <div className="relative w-3.5 h-3.5 shrink-0">
      <div className="absolute inset-0 rounded-full border border-base-line" />
      {active && (
        <div
          className="absolute inset-0 rounded-full animate-radar-sweep"
          style={{ background: 'conic-gradient(from 0deg, transparent 0%, transparent 75%, rgba(55,224,196,0.9) 100%)' }}
        />
      )}
      <div className={`absolute inset-[3px] rounded-full ${active ? 'bg-brand-cyan/20' : 'bg-transparent'}`} />
    </div>
  )
}

export default function NavBar() {
  const loc = useLocation()
  const wsConnected = useStore((s) => s.wsConnected)
  const derivConnected = useStore((s) => s.derivConnected)
  const soundsEnabled = useStore((s) => s.soundsEnabled)
  const setSoundsEnabled = useStore((s) => s.setSoundsEnabled)

  return (
    <nav className="bg-base-panel hairline-b px-3 h-11 flex items-center gap-1 font-condensed text-[13px] tracking-wide uppercase">
      <div className="flex items-center gap-2 pr-3 mr-2 border-r border-base-line h-full">
        <RadarSweep active={wsConnected} />
        <span className="font-mono font-semibold text-text-primary tracking-tight normal-case text-sm">PV TERMINAL</span>
      </div>
      {links.map((l) => (
        <Link
          key={l.to}
          to={l.to}
          className={`px-3 h-full flex items-center border-b-2 transition-colors ${
            loc.pathname === l.to
              ? 'border-brand-cyan text-text-primary'
              : 'border-transparent text-text-secondary hover:text-text-primary hover:border-base-line'
          }`}
        >
          {l.label}
        </Link>
      ))}
      <div className="ml-auto flex items-center gap-3">
        <button
          onClick={() => setSoundsEnabled(!soundsEnabled)}
          className={`w-7 h-7 flex items-center justify-center border transition-colors ${
            soundsEnabled ? 'border-brand-cyan/50 text-brand-cyan' : 'border-base-line text-text-muted hover:text-text-secondary'
          }`}
          title={soundsEnabled ? 'Desactivar sonidos' : 'Activar sonidos'}
        >
          {soundsEnabled ? '♪' : '✕'}
        </button>
        <div className="flex items-center gap-1.5 pl-3 border-l border-base-line h-full">
          <div className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-signal-long animate-pulse-dot' : 'bg-signal-short'}`} />
          <span className="font-mono text-[11px] text-text-secondary normal-case">{wsConnected ? 'LIVE' : 'OFFLINE'}</span>
        </div>
        <div className="flex items-center gap-1.5 pl-3 border-l border-base-line h-full" title={derivConnected ? 'Conectado a Deriv API' : 'Sin conexión a Deriv API'}>
          <div className={`w-1.5 h-1.5 rounded-full ${derivConnected ? 'bg-brand-cyan animate-pulse-dot' : 'bg-base-line'}`} />
          <span className={`font-mono text-[11px] normal-case ${derivConnected ? 'text-brand-cyan' : 'text-text-muted'}`}>
            DERIV {derivConnected ? 'ON' : 'OFF'}
          </span>
        </div>
      </div>
    </nav>
  )
}