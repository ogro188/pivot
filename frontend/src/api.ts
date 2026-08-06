import axios from 'axios'

const API = axios.create({ baseURL: '/api' })

export const fetchAssets = () => API.get('/assets').then((r) => r.data)
export const fetchStrategies = () => API.get('/strategies').then((r) => r.data)
export const startAsset = (s: string) => API.post(`/assets/${s}/start`)
export const stopAsset = (s: string) => API.post(`/assets/${s}/stop`)
export const fetchHistory = (s: string, tf: string, count = 200) =>
  API.get(`/assets/${s}/history`, { params: { tf, count } }).then((r) => r.data)
export const fetchSignals = (s: string, limit = 50) =>
  API.get(`/assets/${s}/signals`, { params: { limit } }).then((r) => r.data)
export const fetchLogs = (s: string, limit = 200) =>
  API.get(`/assets/${s}/consola`, { params: { limit } }).then((r) => r.data)
export const runBacktest = (body: any) => API.post('/backtest', body).then((r) => r.data)
export const getBacktest = (id: string) => API.get(`/backtest/${id}`).then((r) => r.data)
export const fetchParams = (asset: string, strat: string) =>
  API.get(`/assets/${asset}/strategies/${strat}/params`).then((r) => r.data)
export const saveParams = (asset: string, strat: string, body: any) =>
  API.post(`/assets/${asset}/strategies/${strat}/params`, body)
export const configNtfy = (topic: string, server: string) =>
  API.post('/config/ntfy', { topic, server }).then((r) => r.data)

export default API
