"""Cache y cálculo de indicadores técnicos."""
import json
import hashlib
import numpy as np
import pandas as pd


class IndicadorCache:
    def __init__(self):
        self._cache: dict[str, pd.Series] = {}

    def _key(self, nombre: str, config: dict) -> str:
        cfg = json.dumps(config, sort_keys=True)
        h = hashlib.md5(cfg.encode()).hexdigest()[:12]
        return f"{nombre}:{h}"

    def invalidate(self, tf: str) -> None:
        keys = [k for k in self._cache if k.startswith(f"{tf}:")]
        for k in keys:
            del self._cache[k]

    def get(self, df: pd.DataFrame, nombre: str, config: dict) -> pd.Series:
        if df is None or len(df) == 0:
            return pd.Series([np.nan])
        key = f"TF:{self._key(nombre, config)}"
        if key in self._cache:
            return self._cache[key]
        result = self._calcular(df, nombre, config)
        self._cache[key] = result
        return result

    def _calcular(self, df: pd.DataFrame, nombre: str, config: dict) -> pd.Series:
        if nombre == "EMA":
            return self._ema(df, config)
        if nombre == "ATR":
            return self._atr(df, config)
        if nombre == "RSI":
            return self._rsi(df, config)
        raise ValueError(f"Indicador desconocido: {nombre}")

    def _source(self, df: pd.DataFrame, src: str) -> pd.Series:
        if src == "close":
            return df["close"]
        if src == "open":
            return df["open"]
        if src == "high":
            return df["high"]
        if src == "low":
            return df["low"]
        if src == "hl2":
            return (df["high"] + df["low"]) / 2
        if src == "hlc3":
            return (df["high"] + df["low"] + df["close"]) / 3
        if src == "ohlc4":
            return (df["open"] + df["high"] + df["low"] + df["close"]) / 4
        return df["close"]

    def _ema(self, df: pd.DataFrame, config: dict) -> pd.Series:
        periodo = config.get("periodo", 14)
        src = config.get("source", "close")
        if periodo > len(df):
            return pd.Series([np.nan] * len(df))
        s = self._source(df, src)
        return s.ewm(span=periodo, adjust=False).mean()

    def _atr(self, df: pd.DataFrame, config: dict) -> pd.Series:
        periodo = config.get("periodo", 14)
        if periodo > len(df):
            return pd.Series([np.nan] * len(df))
        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        alpha = 1.0 / periodo
        return tr.ewm(alpha=alpha, adjust=False).mean()

    def _rsi(self, df: pd.DataFrame, config: dict) -> pd.Series:
        periodo = config.get("periodo", 14)
        src = config.get("source", "close")
        if periodo > len(df):
            return pd.Series([np.nan] * len(df))
        s = self._source(df, src)
        delta = s.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        alpha = 1.0 / periodo
        avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
        avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
