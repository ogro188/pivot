import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { configNtfy, fetchAssets } from '../api'
import AssetNtfyForm from '../components/AssetNtfyForm'
import {
  Button,
  EmptyState,
  FieldLabel,
  PageHeader,
  Panel,
  QueryState,
  SectionTitle,
  SkeletonCard,
  useToast,
} from '../components/ui'
import { describeError } from '../utils/errors'

export default function ConfigPage() {
  const toast = useToast()
  const [ntfyTopic, setNtfyTopic] = useState('')
  const [ntfyServer, setNtfyServer] = useState('https://ntfy.sh')
  const [saving, setSaving] = useState(false)

  const {
    data: assets,
    isLoading,
    error,
    refetch,
  } = useQuery({ queryKey: ['assets'], queryFn: fetchAssets })

  const handleSaveGlobal = async () => {
    setSaving(true)
    try {
      await configNtfy(ntfyTopic, ntfyServer)
      toast.success('Configuración global de ntfy guardada.', 'Guardado')
    } catch (err) {
      toast.error(describeError(err), 'No se pudo guardar')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Configuración"
        eyebrow="Sistema"
        description="Preferencias globales de notificación y topics por activo."
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 space-y-4">
          <Panel title="ntfy — global" subtitle="Se usa como fallback si un activo no tiene topic">
            <div className="space-y-3">
              <div>
                <FieldLabel htmlFor="ntfy-global-topic">Topic</FieldLabel>
                <input
                  id="ntfy-global-topic"
                  className="w-full bg-base-panel2 border border-base-edge px-2 py-1.5 text-sm text-text-primary"
                  value={ntfyTopic}
                  onChange={(e) => setNtfyTopic(e.target.value)}
                  placeholder="mi-topic-secreto"
                  autoComplete="off"
                />
              </div>
              <div>
                <FieldLabel htmlFor="ntfy-global-server">Server</FieldLabel>
                <input
                  id="ntfy-global-server"
                  className="w-full bg-base-panel2 border border-base-edge px-2 py-1.5 text-sm text-text-primary"
                  value={ntfyServer}
                  onChange={(e) => setNtfyServer(e.target.value)}
                />
              </div>
              <Button
                variant="primary"
                onClick={handleSaveGlobal}
                loading={saving}
                disabled={!ntfyTopic.trim()}
                fullWidth
              >
                Guardar global
              </Button>
            </div>
          </Panel>

          <Panel title="Cómo funciona">
            <ul className="text-[11px] leading-relaxed text-text-secondary space-y-1.5 list-disc list-inside">
              <li>Instalá la app ntfy en tu móvil.</li>
              <li>Suscribite al topic del activo, o al global si no configurás uno propio.</li>
              <li>Cada activo puede tener su propio topic.</li>
              <li>Usá el botón Test de cada activo para comprobar la conexión.</li>
            </ul>
            <p className="text-[10px] leading-relaxed text-text-muted pt-2 mt-2 border-t border-base-line">
              Las notificaciones se envían tanto en modo replay como con Deriv conectado.
            </p>
          </Panel>
        </div>

        <div className="lg:col-span-2 space-y-3">
          <SectionTitle
            aside={
              assets && (
                <span className="tabular text-[10px] text-text-muted">{assets.length} activos</span>
              )
            }
          >
            Topic por activo
          </SectionTitle>

          <QueryState
            loading={isLoading}
            error={error}
            onRetry={() => refetch()}
            errorTitle="No se pudieron cargar los activos"
            isEmpty={!!assets && assets.length === 0}
            empty={
              <EmptyState
                icon="database"
                title="Sin activos configurados"
                description="No hay instrumentos cargados en el sistema."
              />
            }
            skeleton={
              <div className="space-y-3">
                <SkeletonCard />
                <SkeletonCard />
              </div>
            }
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {assets?.map((a: any) => (
                <Panel key={a.simbolo} title={a.simbolo} subtitle={a.nombre} padded>
                  <AssetNtfyForm simbolo={a.simbolo} compact />
                </Panel>
              ))}
            </div>
          </QueryState>
        </div>
      </div>
    </div>
  )
}
