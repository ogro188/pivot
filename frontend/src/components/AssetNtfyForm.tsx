import { useState, useEffect } from 'react'
import { fetchAssetNtfy, saveAssetNtfy, testAssetNtfy } from '../api'
import { Button, FieldLabel, useToast } from './ui'
import { describeError } from '../utils/errors'

interface AssetNtfyFormProps {
  simbolo: string
  compact?: boolean
}

export default function AssetNtfyForm({ simbolo, compact = false }: AssetNtfyFormProps) {
  const toast = useToast()
  const [topic, setTopic] = useState('')
  const [server, setServer] = useState('https://ntfy.sh')
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState<unknown>(null)

  useEffect(() => {
    let cancel = false
    setLoadError(null)
    fetchAssetNtfy(simbolo)
      .then((cfg) => {
        if (cancel) return
        setTopic(cfg.topic || '')
        setServer(cfg.server || 'https://ntfy.sh')
      })
      .catch((err) => {
        if (!cancel) setLoadError(err)
      })
    return () => {
      cancel = true
    }
  }, [simbolo])

  const handleSave = async () => {
    setSaving(true)
    try {
      await saveAssetNtfy(simbolo, topic, server)
      toast.success(`Topic de ${simbolo} guardado.`, 'Guardado')
    } catch (err) {
      toast.error(describeError(err), `No se pudo guardar ${simbolo}`)
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    try {
      const res = await testAssetNtfy(simbolo)
      if (res.ok) {
        toast.success(res.detail || `Notificación enviada a ${simbolo}.`, 'Test enviado')
      } else {
        toast.error(res.detail || 'El servidor ntfy rechazó el mensaje.', 'Test fallido')
      }
    } catch (err) {
      toast.error(describeError(err), 'Sin conexión con ntfy')
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="space-y-2">
      <div>
        <FieldLabel htmlFor={`ntfy-${simbolo}-topic`}>Topic</FieldLabel>
        <input
          id={`ntfy-${simbolo}-topic`}
          className="w-full bg-base-panel2 border border-base-edge px-2 py-1.5 text-xs text-text-primary"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="mi-topic-secreto"
          autoComplete="off"
        />
      </div>
      {!compact && (
        <div>
          <FieldLabel htmlFor={`ntfy-${simbolo}-server`}>Server</FieldLabel>
          <input
            id={`ntfy-${simbolo}-server`}
            className="w-full bg-base-panel2 border border-base-edge px-2 py-1.5 text-xs text-text-primary"
            value={server}
            onChange={(e) => setServer(e.target.value)}
            placeholder="https://ntfy.sh"
          />
        </div>
      )}
      <div className="grid grid-cols-2 gap-2 pt-0.5">
        <Button
          size="sm"
          variant="secondary"
          onClick={handleSave}
          loading={saving}
          fullWidth
        >
          Guardar
        </Button>
        <Button
          size="sm"
          variant="ghost"
          icon="bell"
          onClick={handleTest}
          loading={testing}
          disabled={!topic.trim()}
          fullWidth
        >
          {testing ? 'Probando…' : 'Test'}
        </Button>
      </div>
      {loadError !== null && (
        <p className="text-[10px] text-state-warn" role="status">
          No se pudo leer la config guardada. {describeError(loadError)}
        </p>
      )}
    </div>
  )
}
