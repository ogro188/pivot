import { useState, useEffect } from 'react'
import { fetchAssetNtfy, saveAssetNtfy, testAssetNtfy } from '../api'

interface AssetNtfyFormProps {
  simbolo: string
  compact?: boolean
}

export default function AssetNtfyForm({ simbolo, compact = false }: AssetNtfyFormProps) {
  const [topic, setTopic] = useState('')
  const [server, setServer] = useState('https://ntfy.sh')
  const [status, setStatus] = useState<{ ok: boolean; msg: string } | null>(null)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    fetchAssetNtfy(simbolo).then((cfg) => {
      setTopic(cfg.topic || '')
      setServer(cfg.server || 'https://ntfy.sh')
    }).catch(() => {})
  }, [simbolo])

  const handleSave = async () => {
    try {
      await saveAssetNtfy(simbolo, topic, server)
      setStatus({ ok: true, msg: 'Configuración guardada' })
    } catch {
      setStatus({ ok: false, msg: 'Error al guardar' })
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setStatus(null)
    try {
      const res = await testAssetNtfy(simbolo)
      setStatus({ ok: !!res.ok, msg: res.detail || (res.ok ? 'Notificación enviada' : 'Falló') })
    } catch {
      setStatus({ ok: false, msg: 'Error de conexión' })
    } finally {
      setTesting(false)
    }
  }

  if (compact) {
    return (
      <div className="space-y-1.5">
        <div>
          <label className="block font-condensed text-[10px] tracking-widest text-text-muted uppercase mb-1">Topic</label>
          <input className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-xs text-text-primary" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="mi-topic-secreto" />
        </div>
        <div>
          <label className="block font-condensed text-[10px] tracking-widest text-text-muted uppercase mb-1">Server</label>
          <input className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-xs text-text-primary" value={server} onChange={(e) => setServer(e.target.value)} placeholder="https://ntfy.sh" />
        </div>
        <div className="flex gap-2 pt-1">
          <button onClick={handleSave} className="flex-1 bg-base-panel2 hover:bg-base-line text-text-secondary px-2 py-1 font-condensed text-[10px] tracking-widest uppercase transition-colors">
            Guardar
          </button>
          <button onClick={handleTest} disabled={testing || !topic} className={`flex-1 px-2 py-1 font-condensed text-[10px] tracking-widest uppercase transition-colors ${testing || !topic ? 'bg-base-panel2 border border-base-line text-text-muted cursor-default' : 'border border-brand-cyan/50 text-brand-cyan hover:bg-brand-cyan/10'}`}>
            {testing ? 'Probando…' : 'Test'}
          </button>
        </div>
        {status && (
          <div className={`text-[10px] font-condensed tracking-wide ${status.ok ? 'text-brand-cyan' : 'text-red-400'}`}>
            {status.msg}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="block font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-1">Topic</label>
        <input className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-sm text-text-primary" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="mi-topic-secreto" />
      </div>
      <div>
        <label className="block font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-1">Server</label>
        <input className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-sm text-text-primary" value={server} onChange={(e) => setServer(e.target.value)} />
      </div>
      <button onClick={handleSave} className="border border-brand-cyan/50 text-brand-cyan hover:bg-brand-cyan/10 px-4 py-1.5 font-condensed text-[11px] tracking-widest uppercase transition-colors">
        Guardar
      </button>
      {status && <div className="text-sm text-text-secondary">{status.msg}</div>}
    </div>
  )
}
