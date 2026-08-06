import { useState } from 'react'
import { configNtfy } from '../api'

export default function ConfigPage() {
  const [ntfyTopic, setNtfyTopic] = useState('')
  const [ntfyServer, setNtfyServer] = useState('https://ntfy.sh')
  const [status, setStatus] = useState('')

  const handleSave = async () => {
    try {
      await configNtfy(ntfyTopic, ntfyServer)
      setStatus('Configuración guardada')
    } catch (e) {
      setStatus('Error al guardar')
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Configuración</h1>
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 space-y-4 max-w-xl">
        <h2 className="text-lg font-bold">Notificaciones ntfy</h2>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Topic</label>
          <input className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm" value={ntfyTopic} onChange={(e) => setNtfyTopic(e.target.value)} placeholder="mi-topic-secreto" />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Server</label>
          <input className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm" value={ntfyServer} onChange={(e) => setNtfyServer(e.target.value)} />
        </div>
        <button onClick={handleSave} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm">Guardar</button>
        {status && <div className="text-sm text-gray-400">{status}</div>}
      </div>
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 max-w-xl">
        <h2 className="text-lg font-bold mb-2">Instrucciones rápidas</h2>
        <ul className="text-sm text-gray-400 space-y-1 list-disc list-inside">
          <li>Instala la app ntfy en tu móvil</li>
          <li>Suscribite al topic que pongas arriba</li>
          <li>Cuando una estrategia emita señal, llegará push</li>
          <li>El formato usa separadores visuales para legibilidad</li>
        </ul>
      </div>
    </div>
  )
}
