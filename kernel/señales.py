"""Ciclo de vida de señales: dedup, latch, MFE/MAE."""
import hashlib
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
from kernel.contrato import Señal


def _floor_to_timeframe(dt: datetime, tf: str) -> datetime:
    import pandas as pd
    freq_map = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
                "H1": "1h", "H4": "4h", "D1": "1d"}
    freq = freq_map.get(tf, "15min")
    ts = pd.Timestamp(dt)
    return ts.floor(freq).to_pydatetime()


def _signal_id(sig: Señal, tf_base: str = "M15") -> str:
    vela_ts = _floor_to_timeframe(sig.tiempo, tf_base)
    nivel = sig.nivel_clave if sig.nivel_clave is not None else sig.precio
    raw = f"{sig.estrategia}|{sig.simbolo}|{sig.direccion}|{nivel:.10f}|{vela_ts.isoformat()}"
    return hashlib.md5(raw.encode()).hexdigest()


class Latch:
    def __init__(self):
        self._registro: dict = {}

    def check(self, estrategia: str, simbolo: str, direccion: int,
              nivel_clave: float, vela_ts: datetime, point: float) -> bool:
        key = (estrategia, simbolo, direccion)
        last_nivel, last_vela = self._registro.get(key, (0.0, datetime.min))
        tolerancia = point * 0.5
        if last_vela == vela_ts and abs(last_nivel - nivel_clave) < tolerancia:
            return False
        self._registro[key] = (nivel_clave, vela_ts)
        return True


@dataclass
class Medicion:
    signal_id: int
    offset: int
    retorno: float
    mfe: float
    mae: float


class Medidor:
    def __init__(self, signal: Señal, point: float):
        self.signal = signal
        self.point = point
        self.mediciones: list[Medicion] = []
        self.max_favorable = 0.0
        self.max_adverse = 0.0

    def on_candle(self, vela: pd.Series) -> None:
        offset = len(self.mediciones) + 1
        direccion = self.signal.direccion
        precio = self.signal.precio

        retorno = (vela["close"] - precio) * direccion / self.point

        if direccion == 1:
            max_price = vela["high"]
            min_price = vela["low"]
        else:
            max_price = vela["low"]
            min_price = vela["high"]

        retorno_max = (max_price - precio) * direccion / self.point
        retorno_min = (min_price - precio) * direccion / self.point

        self.max_favorable = max(self.max_favorable, retorno_max)
        self.max_adverse = min(self.max_adverse, retorno_min)

        self.mediciones.append(Medicion(
            signal_id=self.signal.id,
            offset=offset,
            retorno=retorno,
            mfe=self.max_favorable,
            mae=self.max_adverse
        ))

    def resultado(self) -> tuple[bool, float]:
        if not self.mediciones:
            return (False, 0.0)
        final = self.mediciones[-1].retorno
        return (final > 0, final)
