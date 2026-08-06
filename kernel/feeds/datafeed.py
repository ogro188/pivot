"""DataFeed multi-TF con cache de indicadores."""
import threading
from datetime import datetime
import pandas as pd
from kernel.contrato import ActivoInfo, FuenteDatos
from kernel.indicadores import IndicadorCache


class DataFeed:
    def __init__(self, activo: ActivoInfo, fuente: FuenteDatos, max_bars: int = 5000):
        self.activo = activo
        self.fuente = fuente
        self.max_bars = max_bars
        self._velas: dict[str, pd.DataFrame] = {}
        self._lock = threading.RLock()
        self._indicadores = IndicadorCache()

    def inicializar(self) -> None:
        for tf in self.activo.timeframes:
            df = self.fuente.get_candles(tf, self.max_bars)
            with self._lock:
                self._velas[tf] = df
                self._indicadores.invalidate(tf)

    def on_tick(self, precio: float, tiempo: datetime) -> None:
        with self._lock:
            for tf in self._velas:
                df = self._velas[tf]
                if len(df) == 0:
                    continue
                # Crear copia modificada sin alterar el original in-place
                idx = len(df) - 1
                new_close = precio
                new_high = max(df.iloc[idx]["high"], precio)
                new_low = min(df.iloc[idx]["low"], precio)
                df.iloc[idx, df.columns.get_loc("close")] = new_close
                df.iloc[idx, df.columns.get_loc("high")] = new_high
                df.iloc[idx, df.columns.get_loc("low")] = new_low

    def on_candle_close(self, tf: str, vela: pd.Series) -> None:
        with self._lock:
            new_row = vela.to_frame().T
            self._velas[tf] = pd.concat([self._velas[tf], new_row], ignore_index=True).tail(self.max_bars)
            self._indicadores.invalidate(tf)

    def snapshot(self) -> dict[str, pd.DataFrame]:
        with self._lock:
            return {tf: df.copy(deep=False) for tf, df in self._velas.items()}

    def get_indicador(self, tf: str, nombre: str, config: dict) -> pd.Series:
        with self._lock:
            return self._indicadores.get(self._velas[tf], nombre, config)
