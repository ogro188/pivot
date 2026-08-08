import { useEffect, useRef } from 'react'
import { createChart, IChartApi, ISeriesApi, CandlestickData, UTCTimestamp } from 'lightweight-charts'
import { CandleDTO } from '../store'

export default function ChartHost({ candles }: { candles: CandleDTO[] }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      layout: { background: { color: '#111827' }, textColor: '#d1d5db' },
      grid: { vertLines: { color: '#374151' }, horzLines: { color: '#374151' } },
      width: containerRef.current.clientWidth,
      height: 400,
    })
    const series = chart.addCandlestickSeries({
      upColor: '#10b981', downColor: '#ef4444', borderUpColor: '#10b981', borderDownColor: '#ef4444',
      wickUpColor: '#10b981', wickDownColor: '#ef4444'
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
  }, [])

  useEffect(() => {
    if (!seriesRef.current || candles.length === 0) return
    const data: CandlestickData[] = candles.map((c) => ({
      time: c.time as UTCTimestamp,
      open: c.open, high: c.high, low: c.low, close: c.close
    }))
    seriesRef.current.setData(data)
    chartRef.current?.timeScale().fitContent()
  }, [candles])

  return <div ref={containerRef} className="w-full rounded-lg overflow-hidden" />
}
