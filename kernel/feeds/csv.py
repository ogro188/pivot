"""Fuente de datos CSV para backtesting."""
import os
from datetime import datetime
import pandas as pd
from kernel.contrato import FuenteDatos


class CSVFeed(FuenteDatos):
    """Feed CSV robusto: acepta múltiples formatos de fecha y columnas."""

    def __init__(self, path: str):
        self.path = path
        self._df: pd.DataFrame | None = None
        self._idx = 0
        self._conectado = False

    def conectar(self) -> None:
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"CSV no encontrado: {self.path}")
        # Intentar detectar formato
        df = pd.read_csv(self.path)
        # Normalizar columnas
        df.columns = [c.strip().lower() for c in df.columns]
        # Detectar columna de tiempo
        time_cols = [c for c in df.columns if c in ("time", "timestamp", "date", "datetime", "ts")]
        if time_cols:
            df[time_cols[0]] = pd.to_datetime(df[time_cols[0]], utc=True)
            df.set_index(time_cols[0], inplace=True)
        # Asegurar columnas OHLCV
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                df[col] = 0.0
        self._df = df
        self._conectado = True

    def get_candles(self, tf: str, count: int) -> pd.DataFrame:
        if self._df is None:
            raise RuntimeError("No conectado. Llame conectar() primero.")
        return self._df.tail(count).copy()

    def stream(self, on_tick, on_candle, on_error):
        if self._df is None:
            raise RuntimeError("No conectado")
        for ts, row in self._df.iterrows():
            if not self._conectado:
                break
            try:
                on_tick(float(row["close"]), ts if isinstance(ts, datetime) else pd.Timestamp(ts).to_pydatetime())
            except Exception as e:
                on_error(e)
        self._conectado = False

    def stop(self) -> None:
        self._conectado = False

    @property
    def conectado(self) -> bool:
        return self._conectado
