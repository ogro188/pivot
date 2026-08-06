import { Link, useLocation } from 'react-router-dom'
import { useStore } from '../store'

const links = [
  { to: '/', label: 'Hub' },
  { to: '/backtest', label: 'Backtest' },
  { to: '/estrategias', label: 'Estrategias' },
  { to: '/config', label: 'Config' },
]

export default function NavBar() {
  const loc = useLocation()
  const wsConnected = useStore((s) => s.wsConnected)
  return (
    <nav className="bg-gray-800 border-b border-gray-700 px-4 py-2 flex gap-4 items-center">
      {links.map((l) => (
        <Link
          key={l.to}
          to={l.to}
          className={`px-3 py-1 rounded ${loc.pathname === l.to ? 'bg-blue-600 text-white' : 'text-gray-300 hover:text-white'}`}
        >
          {l.label}
        </Link>
      ))}
      <div className="ml-auto flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className="text-xs text-gray-400">{wsConnected ? 'WS' : 'OFF'}</span>
      </div>
    </nav>
  )
}
