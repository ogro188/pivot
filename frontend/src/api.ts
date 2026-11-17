import axios from 'axios'

const API = axios.create({ baseURL: '/api' })

export interface BacktestRequest {
  estrategia: string
  activo: string
  timeframe: string
  fecha_inicio: string
  fecha_fin: string
  capital_inicial?: number
  riesgo_por_operacion?: number
  slippage_pips?: number
  comision_lote?: number
  parametros?: Record<string, any>
}

export interface BacktestSummary {
  id: number
  estrategia: string
  simbolo: string
  timeframe: string
  fecha_inicio: string | null
  fecha_fin: string | null
  capital_inicial: number | null
  capital_final: number | null
  retorno_total: number | null
  win_rate: number | null
  total_operaciones: number | null
  profit_factor: number | null
  sharpe_ratio: number | null
  drawdown_max: number | null
  parametros: Record<string, any>
  metricas: Record<string, any>
  created_at: string | null
}

export interface OperacionDTO {
  id: number
  estrategia: string | null
  simbolo: string | null
  timeframe: string | null
  timestamp_abertura: string | null
  timestamp_cierre: string | null
  tipo: string | null
  precio_entrada: number | null
  precio_salida: number | null
  stop_loss: number | null
  take_profit: number | null
  cantidad: number | null
  pnl: number | null
  estado: string | null
  created_at: string | null
}

export interface OperacionBacktestDTO {
  id: string
  simbolo: string
  direccion: number
  precio_entrada: number
  precio_salida: number | null
  timestamp_entrada: string | null
  timestamp_salida: string | null
  stop_loss: number | null
  take_profit: number | null
  razon_salida: string | null
  pnl_puntos: number
  pnl_dinero: number
  velas_en_operacion: number
}

export interface HealthDTO {
  status: string
  version: string
  strategies_loaded: number
  deriv_connected: boolean
  deriv: any
}

export interface AnaliticaDetectoresDTO {
  total_operaciones: number
  win_rate_general?: number
  top_combinaciones?: { detectores: string; count: number; win_rate: number }[]
}

export interface ResumenDTO {
  senales: number
  operaciones: number
  operaciones_cerradas: number
  operaciones_ganadoras: number
  backtests: number
  winrate: number | null
}

export const fetchAssets = () => API.get('/assets').then((r) => r.data)
export const fetchStrategies = () => API.get('/strategies').then((r) => r.data)
export const startAsset = (s: string, params?: Record<string, any>) =>
  API.post(`/assets/${s}/start`, params || {}).then((r) => r.data)
export const stopAsset = (s: string) => API.post(`/assets/${s}/stop`).then((r) => r.data)
export const fetchHistory = (s: string, tf: string, count = 200) =>
  API.get(`/assets/${s}/history`, { params: { tf, count } }).then((r) => r.data)
export const fetchSignals = (s: string, limit = 50) =>
  API.get(`/assets/${s}/signals`, { params: { limit } }).then((r) => r.data)
export const fetchLogs = (s: string, limit = 200) =>
  API.get(`/assets/${s}/consola`, { params: { limit } }).then((r) => r.data)
export const runBacktest = (body: BacktestRequest) =>
  API.post('/backtest', body).then((r) => r.data)
export const configNtfy = (topic: string, server: string) =>
  API.post('/config/ntfy', { topic, server }).then((r) => r.data)
export const fetchAssetNtfy = (s: string) => API.get(`/assets/${s}/ntfy`).then((r) => r.data)
export const saveAssetNtfy = (s: string, topic: string, server: string) =>
  API.post(`/assets/${s}/ntfy`, { topic, server }).then((r) => r.data)
export const testAssetNtfy = (s: string) =>
  API.post(`/assets/${s}/ntfy/test`).then((r) => r.data)

export const fetchHealth = (): Promise<HealthDTO> => API.get('/health').then((r) => r.data)
export const fetchDerivStatus = () => API.get('/deriv/status').then((r) => r.data)
export const fetchConfig = () => API.get('/config').then((r) => r.data)

export const fetchBacktests = (estrategia?: string, limite = 50): Promise<BacktestSummary[]> =>
  API.get('/backtests', { params: { estrategia, limite } }).then((r) => r.data)
export const fetchBacktest = (id: number): Promise<BacktestSummary> =>
  API.get(`/backtests/${id}`).then((r) => r.data)
export const fetchOperaciones = (
  params: { estrategia?: string; simbolo?: string; limite?: number } = {}
): Promise<OperacionDTO[]> => API.get('/operaciones', { params }).then((r) => r.data)
export const fetchAnaliticaDetectores = (): Promise<AnaliticaDetectoresDTO> =>
  API.get('/analitica/detectores').then((r) => r.data)
export const fetchResumen = (): Promise<ResumenDTO> =>
  API.get('/analitica/resumen').then((r) => r.data)

export default API
