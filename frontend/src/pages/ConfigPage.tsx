import { useEffect, useState } from 'react'
import { configNtfy, fetchAssets, fetchAssetNtfy, saveAssetNtfy, testAssetNtfy } from '../api'

interface AssetNtfyState {
  topic: string
  server: string
  status: { ok: boolean; msg: string } | null
  testing: boolean
}

export default function ConfigPage() {
  const [ntfyTopic, setNtfyTopic] = useState('')
  const [ntfyServer, setNtfyServer] = useState('https://ntfy.sh')
  const [status, setStatus] = useState('')

  const [assets, setAssets] = useState<string[]>([])
  const [ntfyByAsset, setNtfyByAsset] = useState<Record<string, AssetNtfyState>>({})

  useEffect(() => {
    fetchAssets().then((list: any[]) => {
      setAssets(list.map((a) => a.simbolo))
      return list
    }).then((list: any[]) => {
      list.forEach((a) => {
        fetchAssetNtfy(a.simbolo).then((cfg) => {
          setNtfyByAsset((prev) => ({
            ...prev,
            [a.simbolo]: { topic: cfg.topic || '', server: cfg.server || 'https://ntfy.sh', status: null, testing: false },
          }))
        }).catch(() => {})
      })
    }).catch(() => {})
  }, [])

  const updateAsset = (s: string, patch: Partial<AssetNtfyState>) =>
    setNtfyByAsset((prev) => ({ ...prev, [s]: { ...prev[s], ...patch } }))

  const handleSaveGlobal = async () => {
    try {
      await configNtfy(ntfyTopic, ntfyServer)
      setStatus('Configuración guardada')
    } catch (e) {
      setStatus('Error al guardar')
    }
  }

  const handleSaveAsset = async (s: string) => {
    const st = ntfyByAsset[s]
    if (!st) return
    try {
      await saveAssetNtfy(s, st.topic, st.server)
      updateAsset(s, { status: { ok: true, msg: 'Guardado' } })
    } catch {
      updateAsset(s, { status: { ok: false, msg: 'Error al guardar' } })
    }
  }

  const handleTestAsset = async (s: string) => {
    updateAsset(s, { testing: true, status: null })
    try {
      const res = await testAssetNtfy(s)
      updateAsset(s, { status: { ok: !!res.ok, msg: res.detail || (res.ok ? 'Enviada' : 'Falló') }, testing: false })
    } catch {
      updateAsset(s, { status: { ok: false, msg: 'Error de conexión' }, testing: false })
    }
  }

  return (
    <div className="space-y-5">
      <h1 className="font-condensed text-[13px] tracking-widest text-text-muted uppercase">Configuración</h1>

      <div className="panel p-3 space-y-4 max-w-xl">
        <h2 className="font-condensed text-[11px] tracking-widest text-text-secondary uppercase">Notificaciones ntfy — global (fallback)</h2>
        <div>
          <label className="block font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-1">Topic</label>
          <input className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-sm text-text-primary" value={ntfyTopic} onChange={(e) => setNtfyTopic(e.target.value)} placeholder="mi-topic-secreto" />
        </div>
        <div>
          <label className="block font-condensed text-[11px] tracking-widest text-text-muted uppercase mb-1">Server</label>
          <input className="w-full bg-base-panel2 border border-base-line px-2 py-1 text-sm text-text-primary" value={ntfyServer} onChange={(e) => setNtfyServer(e.target.value)} />
        </div>
        <button onClick={handleSaveGlobal} className="border border-brand-cyan/50 text-brand-cyan hover:bg-brand-cyan/10 px-4 py-1.5 font-condensed text-[11px] tracking-widest uppercase transition-colors">Guardar global</button>
        {status && <div className="text-sm text-text-secondary">{status}</div>}
      </div>

      <div className="panel p-3 max-w-2xl">
        <h2 className="font-condensed text-[11px] tracking-widest text-text-secondary uppercase mb-3">Topic por activo</h2>
        <div className="space-y-2">
          {assets.length === 0 && <div className="text-sm text-text-muted">Cargando activos…</div>}
          {assets.map((s) => {
            const st = ntfyByAsset[s]
            if (!st) return null
            return (
              <div key={s} className="border border-base-line bg-base-panel2/50 p-2 space-y-1.5">
                <div className="flex justify-between items-center">
                  <span className="font-mono font-semibold text-sm text-text-primary">{s}</span>
                  {st.status && (
                    <span className={`text-[10px] font-condensed tracking-wide ${st.status.ok ? 'text-emerald-400' : 'text-red-400'}`}>
                      {st.status.msg}
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
                  <div>
                    <label className="block font-condensed text-[10px] tracking-widest text-text-muted uppercase mb-1">Topic</label>
                    <input className="w-full bg-base-panel border border-base-line px-2 py-1 text-xs text-text-primary" value={st.topic} onChange={(e) => updateAsset(s, { topic: e.target.value })} placeholder="topic-del-activo" />
                  </div>
                  <div>
                    <label className="block font-condensed text-[10px] tracking-widest text-text-muted uppercase mb-1">Server</label>
                    <input className="w-full bg-base-panel border border-base-line px-2 py-1 text-xs text-text-primary" value={st.server} onChange={(e) => updateAsset(s, { server: e.target.value })} placeholder="https://ntfy.sh" />
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleSaveAsset(s)} className="flex-1 bg-base-panel2 hover:bg-base-line text-text-secondary px-2 py-1 font-condensed text-[10px] tracking-widest uppercase transition-colors">
                    Guardar
                  </button>
                  <button onClick={() => handleTestAsset(s)} disabled={st.testing || !st.topic} className={`flex-1 px-2 py-1 font-condensed text-[10px] tracking-widest uppercase transition-colors ${st.testing || !st.topic ? 'bg-base-panel2 border border-base-line text-text-muted cursor-default' : 'border border-brand-cyan/50 text-brand-cyan hover:bg-brand-cyan/10'}`}>
                    {st.testing ? 'Probando…' : 'Test'}
                  </button>
                </div>
              </div>
            )
          })}
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
      </div>
    </div>
  )
}
