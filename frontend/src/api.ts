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
  parametros?: Record<string, any>
}

export const fetchAssets = () => API.get('/assets').then((r) => r.data)
export const fetchStrategies = () => API.get('/strategies').then((r) => r.data)
export const startAsset = (s: string) => API.post(`/assets/${s}/start`).then((r) => r.data)
export const stopAsset = (s: string) => API.post(`/assets/${s}/stop`).then((r) => r.data)
export const fetchHistory = (s: string, tf: string, count = 200) =>
  API.get(`/assets/${s}/history`, { params: { tf, count } }).then((r) => r.data)
export const fetchSignals = (s: string, limit = 50) =>
  API.get(`/assets/${s}/signals`, { params: { limit } }).then((r) => r.data)
export const fetchLogs = (s: string, limit = 200) =>
  API.get(`/assets/${s}/consola`, { params: { limit } }).then((r) => r.data)
export const runBacktest = (body: BacktestRequest) => API.post('/backtest', body).then((r) => r.data)
export const configNtfy = (topic: string, server: string) =>
  API.post('/config/ntfy', { topic, server }).then((r) => r.data)

export default API
