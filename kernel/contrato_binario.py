# -*- coding: utf-8 -*-
"""
Kernel de PIVOT - Contratos para Opciones Binarias.
Este módulo define las interfaces específicas para trading de opciones binarias,
donde el resultado depende exclusivamente de la dirección del precio al momento de la expiración.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import pandas as pd


class TipoOpcion(Enum):
    """Tipos de opciones binarias soportadas."""
    CALL = "CALL"  # Precio sube
    PUT = "PUT"    # Precio baja
    ONE_TOUCH = "ONE_TOUCH"      # Toca un nivel antes de expirar
    NO_TOUCH = "NO_TOUCH"        # No toca un nivel antes de expirar
    RANGE = "RANGE"              # Se mantiene dentro de un rango


@dataclass
class ConfiguracionBinaria:
    """Configuración específica para operaciones binarias."""
    # Tiempos de expiración estándar (en minutos)
    expiraciones_soportadas: List[int] = field(default_factory=lambda: [1, 5, 15, 30, 60])
    
    # Payout del broker (ej: 0.80 = 80% de retorno si gana)
    payout_call: float = 0.80
    payout_put: float = 0.80
    
    # Porcentaje de reembolso en caso de empate (ATM)
    reembolso_atm: float = 0.0  # Generalmente 0% en binarias
    
    # Gestión de riesgo
    porcentaje_riesgo: float = 0.02  # 2% por operación
    usar_martingale: bool = False
    martingale_multiplicador: float = 2.0
    martingale_max_nivel: int = 3
    
    # Filtros
    volatilidad_minima: float = 0.0  # ATR mínimo requerido
    volatilidad_maxima: float = 0.0  # ATR máximo permitido
    evitar_noticias: bool = True
    minutos_antes_noticia: int = 30
    minutos_despues_noticia: int = 30


@dataclass
class SeñalBinaria:
    """
    Representa una señal de opción binaria.
    
    Diferencias clave vs Señal tradicional:
    - No tiene stop_loss ni take_profit tradicionales
    - Tiene tiempo de expiración fijo
    - El resultado es binario: WIN/LOSS (o ATM en casos especiales)
    - La dirección es CALL o PUT en lugar de LONG/SHORT
    """
    # Identificación básica
    estrategia: str
    simbolo: str
    tipo_opcion: TipoOpcion  # CALL o PUT principalmente
    precio_entrada: float
    tiempo_entrada: datetime
    
    # Expiración
    expiracion_minutos: int  # Ej: 5, 15, 30, 60
    tiempo_expiracion: datetime = None  # Se calcula automáticamente
    
    # Confianza y scoring
    confianza: float = 50.0  # 0.0 - 100.0
    score: float = 0.0       # Score normalizado 0.0 - 1.0
    
    # Contexto de la señal
    detectores_activos: List[str] = field(default_factory=list)  # Ej: ["D1", "D2", "D3"]
    narrativa: str = ""
    contexto: Dict[str, Any] = field(default_factory=dict)
    
    # Información estructural
    nivel_estructural: float = 0.0  # Nivel clave que generó la señal
    sweep_detectado: bool = False
    fvg_presente: bool = False
    orderblock_presente: bool = False
    
    # Condiciones de mercado
    atr14: float = 0.0
    session: str = ""
    kill_zone: str = ""
    trend_d1: str = "NEUTRO"
    
    # Visualización
    overlays: List[Any] = field(default_factory=list)
    
    # Estado (se actualiza durante el backtest)
    activa: bool = True
    resultado: Optional[str] = None  # "WIN", "LOSS", "ATM" (At The Money)
    precio_expiracion: Optional[float] = None
    pnl_porcentual: Optional[float] = None  # +80%, -100%, etc.
    
    # Metadata
    id_señal: Optional[str] = None
    timestamp_creacion: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __post_init__(self):
        """Calcula el tiempo de expiración y genera ID único."""
        if self.tiempo_expiracion is None:
            self.tiempo_expiracion = self.tiempo_entrada + timedelta(minutes=self.expiracion_minutos)
        
        if self.id_señal is None:
            import hashlib
            contenido = f"{self.estrategia}_{self.simbolo}_{self.tiempo_entrada.strftime('%Y%m%d_%H%M')}_{self.tipo_opcion.value}"
            hash_suffix = hashlib.md5(contenido.encode()).hexdigest()[:6]
            self.id_señal = f"BIN_{self.estrategia}_{self.simbolo}_{self.tiempo_entrada.strftime('%Y%m%d_%H%M')}_{hash_suffix}"
    
    @property
    def direccion_int(self) -> int:
        """Convierte tipo de opción a entero para compatibilidad."""
        return 1 if self.tipo_opcion == TipoOpcion.CALL else -1
    
    def evaluar_resultado(self, precio_cierre: float) -> str:
        """
        Evalúa el resultado de la operación basado en el precio de cierre.
        
        Args:
            precio_cierre: Precio del activo al momento de la expiración
        
        Returns:
            "WIN", "LOSS", o "ATM" (At The Money - empate)
        """
        if self.tipo_opcion == TipoOpcion.CALL:
            if precio_cierre > self.precio_entrada:
                return "WIN"
            elif precio_cierre < self.precio_entrada:
                return "LOSS"
            else:
                return "ATM"
        elif self.tipo_opcion == TipoOpcion.PUT:
            if precio_cierre < self.precio_entrada:
                return "WIN"
            elif precio_cierre > self.precio_entrada:
                return "LOSS"
            else:
                return "ATM"
        else:
            # Para otros tipos de opciones, se requiere lógica específica
            return "LOSS"
    
    def calcular_pnl(self, resultado: str, payout: float = 0.80) -> float:
        """
        Calcula el PnL porcentual basado en el resultado.
        
        Args:
            resultado: "WIN", "LOSS", o "ATM"
            payout: Porcentaje de pago del broker (ej: 0.80 = 80%)
        
        Returns:
            PnL como porcentaje del capital arriesgado (ej: +80, -100, 0)
        """
        if resultado == "WIN":
            return payout * 100  # ej: +80%
        elif resultado == "LOSS":
            return -100.0  # Pierde todo el capital arriesgado
        else:  # ATM
            return 0.0  # Generalmente reembolsan el 100%


@dataclass
class OperacionBinaria:
    """Representa una operación binaria abierta o cerrada."""
    id_operacion: str
    señal: SeñalBinaria
    simbolo: str
    tipo_opcion: TipoOpcion
    precio_entrada: float
    timestamp_entrada: datetime
    
    # Configuración de la operación
    expiracion_minutos: int
    timestamp_expiracion: datetime
    capital_arriesgado: float = 0.0  # Dinero real apostado
    payout_esperado: float = 0.80    # Payout del broker
    
    # Estado
    precio_expiracion: Optional[float] = None
    resultado: Optional[str] = None  # "WIN", "LOSS", "ATM"
    pnl_porcentual: Optional[float] = None
    pnl_dinero: Optional[float] = None
    velas_en_operacion: int = 0
    
    def __post_init__(self):
        if self.id_operacion is None:
            self.id_operacion = f"BOP_{self.timestamp_entrada.strftime('%Y%m%d_%H%M%S')}"


@dataclass
class ResultadoBacktestBinario:
    """Resultados completos de un backtest de opciones binarias."""
    # Configuración
    estrategia: str
    simbolo: str
    periodo_inicio: datetime
    periodo_fin: datetime
    timeframe_principal: str
    
    # Capital
    capital_inicial: float = 0.0
    capital_final: float = 0.0
    
    # Métricas principales específicas de binarias
    total_operaciones: int = 0
    operaciones_ganadoras: int = 0
    operaciones_perdedoras: int = 0
    operaciones_empate: int = 0  # ATM
    winrate: float = 0.0         # Porcentaje de aciertos
    
    # Rentabilidad
    retorno_total: float = 0.0           # % total
    retorno_promedio: float = 0.0        # % por operación
    profit_factor: float = 0.0           # Ganancias / Pérdidas
    expectativa_matematica: float = 0.0  # Valor esperado por operación
    
    # Riesgo y consistencia
    racha_ganadora_max: int = 0
    racha_perdedora_max: int = 0
    drawdown_maximo: float = 0.0         # Máxima caída del capital
    sharpe_ratio: float = 0.0
    
    # Análisis por tipo de setup
    estadisticas_por_detector: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    estadisticas_por_expiracion: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    estadisticas_por_sesion: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Detalles
    operaciones: List[OperacionBinaria] = field(default_factory=list)
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para serialización JSON."""
        return {
            "estrategia": self.estrategia,
            "simbolo": self.simbolo,
            "periodo_inicio": self.periodo_inicio.isoformat(),
            "periodo_fin": self.periodo_fin.isoformat(),
            "timeframe_principal": self.timeframe_principal,
            "total_operaciones": self.total_operaciones,
            "operaciones_ganadoras": self.operaciones_ganadoras,
            "operaciones_perdedoras": self.operaciones_perdedoras,
            "operaciones_empate": self.operaciones_empate,
            "winrate": round(self.winrate, 2),
            "retorno_total": round(self.retorno_total, 2),
            "retorno_promedio": round(self.retorno_promedio, 2),
            "profit_factor": round(self.profit_factor, 2),
            "expectativa_matematica": round(self.expectativa_matematica, 2),
            "drawdown_maximo": round(self.drawdown_maximo, 2),
            "racha_ganadora_max": self.racha_ganadora_max,
            "racha_perdedora_max": self.racha_perdedora_max,
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "estadisticas_por_detector": self.estadisticas_por_detector,
            "estadisticas_por_expiracion": {str(k): v for k, v in self.estadisticas_por_expiracion.items()},
            "estadisticas_por_sesion": self.estadisticas_por_sesion,
        }


# =============================================================================
# CLASE ABSTRACTA DE ESTRATEGIA BINARIA
# =============================================================================

class EstrategiaBinaria(ABC):
    """
    Clase base abstracta para estrategias de opciones binarias.
    
    Diferencias con Estrategia tradicional:
    - Genera SeñalesBinarias en lugar de Señales
    - No requiere calcular SL/TP
    - Debe especificar tiempo de expiración óptimo
    - Enfocada en probabilidad direccional pura
    """
    
    # Metadatos
    nombre: str = "binaria_base"
    version: str = "1.0"
    timeframes: List[str] = ["M15"]
    eventos: List[str] = ["candle_close"]
    
    # Parámetros configurables
    parametros: Dict[str, Dict[str, Any]] = {}
    
    @abstractmethod
    def setup(self, params: Dict[str, Any], activo: Any, config_binaria: ConfiguracionBinaria) -> None:
        """
        Inicializa la estrategia con parámetros y configuración binaria.
        
        Args:
            params: Diccionario de parámetros de la estrategia
            activo: Información del activo
            config_binaria: Configuración específica para binarias
        """
        pass
    
    @abstractmethod
    def detectar(self, ctx: Any) -> List[SeñalBinaria]:
        """
        Evalúa el contexto y genera señales de opciones binarias.
        
        Args:
            ctx: Contexto de mercado actual
            
        Returns:
            Lista de señales binarias generadas
        """
        pass
    
    def on_backtest_tick(self, ctx: Any, operacion_abierta: bool) -> List[SeñalBinaria]:
        """Hook especial para backtesting (opcional)."""
        return self.detectar(ctx)
    
    def obtener_expiracion_optima(self, ctx: Any, detectores: List[str]) -> int:
        """
        Sugiere el tiempo de expiración óptimo basado en el contexto.
        
        Regla general:
        - Patrones en M1-M5 → Expiración 5-15 min
        - Patrones en M15-M30 → Expiración 15-30 min
        - Patrones en H1-H4 → Expiración 30-60 min
        
        Args:
            ctx: Contexto actual
            detectores: Lista de detectores que activaron la señal
            
        Returns:
            Tiempo de expiración en minutos
        """
        # Implementación por defecto: 15 minutos
        return 15
    
    def filtrar_por_volatilidad(self, ctx: Any, config: ConfiguracionBinaria) -> bool:
        """
        Verifica si la volatilidad actual está dentro de los rangos aceptables.
        
        Returns:
            True si la volatilidad es adecuada, False si se debe filtrar
        """
        if not hasattr(ctx, 'g_atr14_buffer') or not ctx.g_atr14_buffer:
            return True  # Sin datos, permitir por defecto
        
        atr_actual = ctx.g_atr14_buffer[0]
        
        if config.volatilidad_minima > 0 and atr_actual < config.volatilidad_minima:
            return False  # Volatilidad muy baja (riesgo de rango lateral)
        
        if config.volatilidad_maxima > 0 and atr_actual > config.volatilidad_maxima:
            return False  # Volatilidad muy alta (riesgo de ruido)
        
        return True
