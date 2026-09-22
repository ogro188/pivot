import { useEffect, useState } from 'react'
import { configNtfy, fetchAssets } from '../api'
import AssetNtfyForm from '../components/AssetNtfyForm'

export default function ConfigPage() {
  const [ntfyTopic, setNtfyTopic] = useState('')
  const [ntfyServer, setNtfyServer] = useState('https://ntfy.sh')
  const [status, setStatus] = useState('')
  const [assets, setAssets] = useState<string[]>([])

  useEffect(() => {
    fetchAssets().then((list: any[]) => {
      setAssets(list.map((a) => a.simbolo))
    }).catch(() => {})
  }, [])

  const handleSaveGlobal = async () => {
    try {
      await configNtfy(ntfyTopic, ntfyServer)
      setStatus('Configuración guardada')
    } catch {
      setStatus('Error al guardar')
    }
  }

  return (
    <div className="space-y-5">
      <h1 className="font-condensed text-[13px] tracking-widest text-text-muted uppercase">Configuración</h1>

      <div className="panel p-3 space-y-4 max-w-xl">
        <h2 className="font-condensed text-[11px] tracking-widest text-text-secondary uppercase">Notificaciones ntfy — global (fallback)</h2>
        <div>
          <label htmlFor="ntfy-global-topic" className="block font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-1">Topic</label>
          <input id="ntfy-global-topic" className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-sm text-text-primary" value={ntfyTopic} onChange={(e) => setNtfyTopic(e.target.value)} placeholder="mi-topic-secreto" />
        </div>
        <div>
          <label htmlFor="ntfy-global-server" className="block font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-1">Server</label>
          <input id="ntfy-global-server" className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-sm text-text-primary" value={ntfyServer} onChange={(e) => setNtfyServer(e.target.value)} />
        </div>
        <button onClick={handleSaveGlobal} className="border border-brand-cyan/50 text-brand-cyan hover:bg-brand-cyan/10 px-4 py-1.5 font-condensed text-[11px] tracking-widest uppercase transition-colors">Guardar global</button>
        {status && <div className="text-sm text-text-secondary">{status}</div>}
      </div>

      <div className="panel p-3 max-w-2xl">
        <h2 className="font-condensed text-[11px] tracking-widest text-text-secondary uppercase mb-3">Topic por activo</h2>
        <div className="space-y-3">
          {assets.length === 0 && <div className="text-sm text-text-muted">Cargando activos…</div>}
          {assets.map((s) => (
            <div key={s} className="border border-base-line bg-base-panel2/50 p-2">
              <div className="font-mono font-semibold text-sm text-text-primary mb-2">{s}</div>
              <AssetNtfyForm simbolo={s} compact />
            </div>
          ))}
        </div>
      </div>

      <div className="panel p-3 max-w-xl">
        <h2 className="font-condensed text-[11px] tracking-widest text-text-secondary uppercase mb-2">Instrucciones rápidas</h2>
        <ul className="font-condensed text-[11px] text-text-secondary space-y-1 list-disc list-inside normal-case">
          <li>Instala la app ntfy en tu móvil</li>
          <li>Suscribite al topic del activo (o al global si no configurás uno propio)</li>
          <li>Cada activo puede tener su propio topic; las señales de ese activo se envían ahí</li>
          <li>Usa el botón Test para comprobar la conexión</li>
        </ul>
        <p className="font-condensed text-[10px] text-text-muted tracking-wide pt-2 border-t border-base-line">
          Las notificaciones se envían tanto en modo replay como con Deriv conectado.
        </p>
      </div>
    </div>
  )
}
