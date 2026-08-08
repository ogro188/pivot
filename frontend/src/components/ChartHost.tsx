import { useEffect, useRef } from 'react'
import { createChart, IChartApi, ISeriesApi, CandlestickData, UTCTimestamp, SeriesMarker } from 'lightweight-charts'
import { CandleDTO, SignalDTO, AssetDTO } from '../store'

interface ChartHostProps {
  candles: CandleDTO[]
  signals?: SignalDTO[]
  height?: number
  asset?: AssetDTO
}

export default function ChartHost({ candles, signals = [], height = 400, asset }: ChartHostProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      layout: { background: { color: '#111827' }, textColor: '#d1d5db' },
      grid: { vertLines: { color: '#374151' }, horzLines: { color: '#374151' } },
      width: containerRef.current.clientWidth,
      height,
    })
    const priceFormat = asset
      ? {
          type: 'price' as const,
          precision: Math.max(0, Math.round(-Math.log10(asset.punto))),
          minMove: asset.tick_size || asset.punto,
        }
      : { type: 'price' as const, precision: 2, minMove: 0.01 }
    const series = chart.addCandlestickSeries({
      upColor: '#10b981', downColor: '#ef4444', borderUpColor: '#10b981', borderDownColor: '#ef4444',
      wickUpColor: '#10b981', wickDownColor: '#ef4444',
      priceFormat,
    })
    chartRef.current = chart
    seriesRef.current = series
    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)
    return () => { window.removeEventListener('resize', handleResize); chart.remove() }
  }, [height, asset])

  useEffect(() => {
    if (!seriesRef.current || candles.length === 0) return
    const data: CandlestickData[] = candles.map((c) => ({
      time: c.time as UTCTimestamp,
      open: c.open, high: c.high, low: c.low, close: c.close
    }))
    seriesRef.current.setData(data)
    chartRef.current?.timeScale().fitContent()
  }, [candles])

  // Actualizar markers de señales
  useEffect(() => {
    if (!seriesRef.current || signals.length === 0) return
    const markers: SeriesMarker<UTCTimestamp>[] = signals
      .filter((s) => s.ts && s.precio)
      .map((s) => {
        const timeSec = Math.floor(s.ts / 1000) // lightweight-charts usa segundos
        const isLong = s.direccion === 1
        return {
          time: timeSec as UTCTimestamp,
          position: isLong ? 'belowBar' : 'aboveBar',
          color: isLong ? '#10b981' : '#ef4444',
          shape: 'circle' as const,
          text: s.etiqueta?.replace('PIVOT_', '') || 'S',
        }
      })
    seriesRef.current.setMarkers(markers)
  }, [signals])

  return <div ref={containerRef} className="w-full rounded-lg overflow-hidden" />
}
