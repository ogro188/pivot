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
    <div className="space-y-5">
      <h1 className="font-condensed text-[13px] tracking-widest text-text-muted uppercase">Configuración</h1>
      <div className="panel p-3 space-y-4 max-w-xl">
        <h2 className="font-condensed text-[11px] tracking-widest text-text-secondary uppercase">Notificaciones ntfy</h2>
        <div>
          <label className="block font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-1">Topic</label>
          <input className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-sm text-text-primary" value={ntfyTopic} onChange={(e) => setNtfyTopic(e.target.value)} placeholder="mi-topic-secreto" />
        </div>
        <div>
          <label className="block font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-1">Server</label>
          <input className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-sm text-text-primary" value={ntfyServer} onChange={(e) => setNtfyServer(e.target.value)} />
        </div>
        <button onClick={handleSave} className="border border-brand-cyan/50 text-brand-cyan hover:bg-brand-cyan/10 px-4 py-1.5 font-condensed text-[11px] tracking-widest uppercase transition-colors">Guardar</button>
        {status && <div className="text-sm text-text-secondary">{status}</div>}
      </div>
      <div className="panel p-3 max-w-xl">
        <h2 className="font-condensed text-[11px] tracking-widest text-text-secondary uppercase mb-2">Instrucciones rápidas</h2>
        <ul className="font-condensed text-[11px] text-text-secondary space-y-1 list-disc list-inside normal-case">
          <li>Instala la app ntfy en tu móvil</li>
          <li>Suscribite al topic que pongas arriba</li>
          <li>Cuando una estrategia emita señal, llegará push</li>
          <li>El formato usa separadores visuales para legibilidad</li>
        </ul>
      </div>
    </div>
  )
}