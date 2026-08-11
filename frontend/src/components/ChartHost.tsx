import { useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react'
import { ChartView, DrawingToolbar, IndicatorController, IndicatorPicker, createBuiltinRegistry, type ChartController } from '@getcandlekit/charts/react'
import { createSeriesMarkers, ISeriesApi, ISeriesMarkersPluginApi, UTCTimestamp, SeriesMarker } from 'lightweight-charts'
import { CandleDTO, SignalDTO, AssetDTO } from '../store'

interface ChartHostProps {
  candles: CandleDTO[]
  signals?: SignalDTO[]
  height?: number
  asset?: AssetDTO
  id?: string
}

function toChartBar(c: CandleDTO) {
  return {
    ts: c.time * 1000,
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
    volume: c.volume ?? 0,
  }
}

export default function ChartHost({ candles, signals = [], height = 400, asset, id }: ChartHostProps) {
  const markersRef = useRef<ISeriesMarkersPluginApi<UTCTimestamp> | null>(null)
  const controllerRef = useRef<ChartController | null>(null)
  const idRef = useRef(id)
  const [ready, setReady] = useState(false)
  const storageKey = `drawings:${id || asset?.simbolo || 'chart'}`

  const indicators = useMemo(() => {
    const c = new IndicatorController(createBuiltinRegistry())
    c.add('EMA', { length: 50 })
    c.add('EMA', { length: 200 })
    return c
  }, [])

  // La vela formándose se actualiza con updateBar (sin resetear el zoom).
  // El setData solo ocurre cuando cambian las velas cerradas (una vez por vela).
  const forming = candles.length > 0 ? candles[candles.length - 1] : undefined
  const closed = candles.length > 1 ? candles.slice(0, -1) : []
  const closedKey = useMemo(
    () => closed.map((c) => `${c.time},${c.open},${c.high},${c.low},${c.close}`).join('|'),
    [closed]
  )

  const data = useMemo(() => closed.map(toChartBar), [closedKey])

  // Cambio de símbolo / timeframe: re-ajustar el rango visible.
  useEffect(() => {
    if (idRef.current === id) return
    idRef.current = id
    const ctl = controllerRef.current
    if (ctl) {
      requestAnimationFrame(() => ctl.getChart().timeScale().fitContent())
    }
  }, [id])

  // Live: actualizar solo la última vela formándose sin resetear el zoom.
  useEffect(() => {
    const ctl = controllerRef.current
    if (!ctl || !forming) return
    ctl.updateBar(toChartBar(forming))
  }, [forming])

  return (
    <ChartView
      data={data}
      seriesType="candlestick"
      theme="dark"
      showVolume
      autoFit
      drawing={{ storageKey }}
      indicators={indicators}
      style={{ height, width: '100%' }}
      className="w-full rounded-sm overflow-hidden"
      onReady={({ controller }) => {
        controllerRef.current = controller
        if (asset) {
          controller.getSeries().applyOptions({
            priceFormat: {
              type: 'price',
              precision: Math.max(0, Math.round(-Math.log10(asset.punto))),
              minMove: asset.tick_size || asset.punto,
            },
          })
        }
        markersRef.current = createSeriesMarkers<UTCTimestamp>(controller.getSeries() as ISeriesApi<'Candlestick', UTCTimestamp>, [])
        setReady(true)
      }}
    >
      <DrawingToolbar />
      <IndicatorPicker />
      <SignalsMarkers signals={signals} targets={markersRef} ready={ready} />
    </ChartView>
  )
}

function SignalsMarkers({ signals, targets, ready }: { signals: SignalDTO[]; targets: MutableRefObject<ISeriesMarkersPluginApi<UTCTimestamp> | null>; ready: boolean }) {
  useEffect(() => {
    const api = targets.current
    if (!ready || !api) return
    const markers: SeriesMarker<UTCTimestamp>[] = signals
      .filter((s) => s.ts && s.precio)
      .map((s) => {
        const isLong = s.direccion === 1
        return {
          time: Math.floor(s.ts / 1000) as UTCTimestamp,
          position: isLong ? 'belowBar' : 'aboveBar',
          color: isLong ? '#10b981' : '#ef4444',
          shape: 'circle',
          text: s.etiqueta?.replace('PIVOT_', '') || 'S',
        }
      })
    api.setMarkers(markers)
  }, [signals, targets, ready])

  return null
}
