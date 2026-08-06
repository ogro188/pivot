"""Contratos de tipos del kernel RADAR."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
import pandas as pd


@dataclass(frozen=True)
class ActivoInfo:
    simbolo: str
    nombre: str
    point: float
    decimales: int
    pip: float
    fuente_tipo: str
    fuente_config: dict
    timeframes: list
    horario_broker_utc: int


@dataclass
class Metrica:
    label: str
    value: float
    max: float | None = None
    unit: str = ""


@dataclass
class Overlay:
    tipo: str
    color: str = "#2962FF"
    position: str = ""
    shape: str = ""
    text: str = ""
    price: float = 0.0
    line_type: str = ""
    style: str = "solid"
    title: str = ""
    top: float = 0.0
    bottom: float = 0.0
    label: str = ""


@dataclass
class Señal:
    estrategia: str
    simbolo: str
    direccion: int
    precio: float
    tiempo: datetime
    expiracion_velas: int
    confianza: tuple
    objetivo: float | None = None
    invalidacion: float | None = None
    nivel_clave: float | None = None
    etiqueta: str = ""
    narrativa: str = ""
    metricas: list = field(default_factory=list)
    overlays: list = field(default_factory=list)
    payload: dict = field(default_factory=dict)
    id: int = 0
    estado: str = "pending"


@dataclass
class Contexto:
    activo: ActivoInfo
    velas: dict
    precio: float
    tiempo: datetime
    evento: str
    session: str
    kill_zone: str

    def indicador(self, tf: str, nombre: str, config: dict) -> pd.Series:
        raise NotImplementedError("indicador debe ser inyectado por el DataFeed")


class Estrategia(ABC):
    nombre: str = ""
    version: str = "1.0"
    descripcion: str = ""
    timeframes: list = ["M15"]
    max_bars_hist: int = 500
    eventos: list = ["candle_close"]
    timeout_ms: int = 500
    parametros: dict = {}

    def setup(self, params: dict[str, Any], activo: ActivoInfo) -> None:
        pass

    @abstractmethod
    def detectar(self, ctx: Contexto) -> list[Señal]:
        ...

    def nivel_clave(self, sig: Señal) -> float | None:
        return sig.nivel_clave if sig.nivel_clave is not None else sig.precio

    def teardown(self) -> None:
        pass


class FuenteDatos(ABC):
    @abstractmethod
    def conectar(self) -> None:
        ...

    @abstractmethod
    def get_candles(self, tf: str, count: int) -> pd.DataFrame:
        ...

    @abstractmethod
    def stream(self, on_tick, on_candle, on_error) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...

    @property
    @abstractmethod
    def conectado(self) -> bool:
        ...
