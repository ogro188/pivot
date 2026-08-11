import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface SignalDTO {
  id: string | number; ts: number; asset: string; estrategia: string; etiqueta: string;
  direccion: number; precio: number; expiracion_velas: number;
  confianza: [number, number]; objetivo?: number; invalidacion?: number;
  narrativa: string; estado: string; detectores?: string[];
  conviccion?: string; timeframe?: string;
}

export interface AssetDTO {
  simbolo: string; nombre: string; running: boolean; connected: boolean;
  price: number; session: string; kill_zone: string;
  strategies_active: number; signals_today: number;
  decimales?: number;
  punto: number;
  tick_size: number;
  fuente?: string;
  deriv_connected?: boolean;
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
  derivConnected: boolean;
  derivAssets: Record<string, any>;
  // Sonidos
  soundsEnabled: boolean;
  soundQueue: SignalDTO[];
  // Config por activo
  assetConfig: Record<string, Record<string, any>>;
  // Push notifications
  pushNotificationsEnabled: boolean;
  // Actions
  setAssetPrice: (simbolo: string, price: number) => void;
  addSignal: (signal: SignalDTO) => void;
  setAssets: (assets: AssetDTO[]) => void;
  setCandles: (simbolo: string, tf: string, candles: CandleDTO[]) => void;
  upsertCandle: (simbolo: string, tf: string, candle: CandleDTO) => void;
  addLog: (log: LogEntryDTO) => void;
  setWsConnected: (c: boolean) => void;
  setDerivConnected: (c: boolean) => void;
  setDerivAssets: (assets: Record<string, any>) => void;
  // Sound actions
  setSoundsEnabled: (enabled: boolean) => void;
  clearSoundQueue: () => void;
  // Asset config actions
  setAssetConfig: (simbolo: string, params: Record<string, any>) => void;
  getAssetConfig: (simbolo: string) => Record<string, any>;
  // Push notification actions
  setPushNotificationsEnabled: (enabled: boolean) => void;
}

export const useStore = create<AppStore>()(
  persist(
    (set, get) => ({
      assets: {},
      globalSignals: [],
      activeAsset: null,
      candles: {},
      signals: [],
      consoleLogs: [],
      overlays: [],
      backtestJobs: {},
      wsConnected: false,
      derivConnected: false,
      derivAssets: {},
      // Sonidos
      soundsEnabled: false,
      soundQueue: [],
      // Config por activo
      assetConfig: {},
      // Push notifications
      pushNotificationsEnabled: false,
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
      upsertCandle: (simbolo, tf, candle) =>
        set((s) => {
          const key = `${simbolo}:${tf}`
          const existing = s.candles[key] || []
          const idx = existing.findIndex((c) => c.time === candle.time)
          const next =
            idx === -1
              ? [...existing, candle].sort((a, b) => a.time - b.time)
              : existing.map((c, i) => (i === idx ? candle : c))
          return { candles: { ...s.candles, [key]: next.slice(-300) } }
        }),
      addLog: (log) =>
        set((s) => ({ consoleLogs: [log, ...s.consoleLogs].slice(0, 800) })),
      setWsConnected: (c) => set({ wsConnected: c }),
      setDerivConnected: (c) => set({ derivConnected: c }),
      setDerivAssets: (assets) => set({ derivAssets: assets }),
      // Sound actions
      setSoundsEnabled: (enabled) =>
        set((s) => ({ soundsEnabled: enabled, soundQueue: enabled ? [] : s.soundQueue })),
      clearSoundQueue: () => set({ soundQueue: [] }),
      // Asset config actions
      setAssetConfig: (simbolo, params) =>
        set((s) => ({ assetConfig: { ...s.assetConfig, [simbolo]: params } })),
      getAssetConfig: (simbolo) => get().assetConfig[simbolo] || {},
      // Push notification actions
      setPushNotificationsEnabled: (enabled) => set({ pushNotificationsEnabled: enabled }),
    }),
    {
      name: 'pivot-frontend-storage',
      partialize: (state) => ({
        assetConfig: state.assetConfig,
        pushNotificationsEnabled: state.pushNotificationsEnabled,
        soundsEnabled: state.soundsEnabled,
      }),
    }
  )
)
