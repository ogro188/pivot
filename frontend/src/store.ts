import { create } from 'zustand'

export interface SignalDTO {
  id: number; ts: number; asset: string; estrategia: string; etiqueta: string;
  direccion: number; precio: number; expiracion_velas: number;
  confianza: [number, number]; objetivo?: number; invalidacion?: number;
  narrativa: string; estado: string;
}

export interface AssetDTO {
  simbolo: string; nombre: string; running: boolean; connected: boolean;
  price: number; session: string; kill_zone: string;
  strategies_active: number; signals_today: number;
}

export interface CandleDTO {
  time: number; open: number; high: number; low: number; close: number; volume: number;
}

export interface LogEntryDTO {
  ts: number; t: string; level: string; cat: string; msg: string; est?: string;
}

interface AppStore {
  assets: Record<string, AssetDTO>;
  globalSignals: SignalDTO[];
  activeAsset: string | null;
  candles: Record<string, CandleDTO[]>;
  signals: SignalDTO[];
  consoleLogs: LogEntryDTO[];
  overlays: any[];
  backtestJobs: Record<string, any>;
  wsConnected: boolean;
  setAssetPrice: (simbolo: string, price: number) => void;
  addSignal: (signal: SignalDTO) => void;
  setAssets: (assets: AssetDTO[]) => void;
  setCandles: (simbolo: string, tf: string, candles: CandleDTO[]) => void;
  addLog: (log: LogEntryDTO) => void;
  setWsConnected: (c: boolean) => void;
}

export const useStore = create<AppStore>((set) => ({
  assets: {},
  globalSignals: [],
  activeAsset: null,
  candles: {},
  signals: [],
  consoleLogs: [],
  overlays: [],
  backtestJobs: {},
  wsConnected: false,
  setAssetPrice: (simbolo, price) =>
    set((s) => ({ assets: { ...s.assets, [simbolo]: { ...s.assets[simbolo], price } } })),
  addSignal: (signal) =>
    set((s) => ({ globalSignals: [signal, ...s.globalSignals].slice(0, 200) })),
  setAssets: (assets) =>
    set((s) => {
      const map: Record<string, AssetDTO> = {};
      assets.forEach((a) => (map[a.simbolo] = a));
      return { assets: map };
    }),
  setCandles: (simbolo, tf, candles) =>
    set((s) => ({ candles: { ...s.candles, [`${simbolo}:${tf}`]: candles } })),
  addLog: (log) =>
    set((s) => ({ consoleLogs: [log, ...s.consoleLogs].slice(0, 800) })),
  setWsConnected: (c) => set({ wsConnected: c }),
}))
