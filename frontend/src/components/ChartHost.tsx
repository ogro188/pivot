import { useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react'
import { ChartView, DrawingToolbar, IndicatorController, IndicatorPicker, createBuiltinRegistry } from '@getcandlekit/charts/react'
import { createSeriesMarkers, ISeriesApi, ISeriesMarkersPluginApi, UTCTimestamp, SeriesMarker } from 'lightweight-charts'
import { CandleDTO, SignalDTO, AssetDTO } from '../store'

interface ChartHostProps {
  candles: CandleDTO[]
  signals?: SignalDTO[]
  height?: number
  asset?: AssetDTO
  id?: string
}

export default function ChartHost({ candles, signals = [], height = 400, asset, id }: ChartHostProps) {
  const markersRef = useRef<ISeriesMarkersPluginApi<UTCTimestamp> | null>(null)
  const [ready, setReady] = useState(false)
  const storageKey = `drawings:${id || asset?.simbolo || 'chart'}`

  const indicators = useMemo(() => {
    const c = new IndicatorController(createBuiltinRegistry())
    c.add('EMA', { length: 50 })
    c.add('EMA', { length: 200 })
    return c
  }, [])

  const data = useMemo(
    () =>
      candles.map((c) => ({
        ts: c.time * 1000,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume,
      })),
    [candles]
  )

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
      className="w-full rounded-lg overflow-hidden"
      onReady={({ controller }) => {
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