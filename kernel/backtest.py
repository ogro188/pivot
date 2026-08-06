# -*- coding: utf-8 -*-
"""
Kernel de PIVOT - Motor de Backtesting Profesional.
Ejecuta estrategias sobre datos históricos y calcula métricas de rendimiento.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from copy import deepcopy

from kernel.contrato import Contexto, Señal, ActivoInfo, Estrategia, Overlay, Metrica
from kernel.feeds.csv import CSVFeed, MultiTimeframeFeed


@dataclass
class Operacion:
    """Representa una operación abierta o cerrada."""
    id_operacion: str
    señal: Señal
    simbolo: str
    direccion: int  # 1 = LONG, -1 = SHORT
    precio_entrada: float
    timestamp_entrada: datetime
    stop_loss: Optional[float]
    take_profit: Optional[float]
    
    # Estado
    precio_salida: Optional[float] = None
    timestamp_salida: Optional[datetime] = None
    razon_salida: str = ""  # "TP", "SL", "EXPIRED", "MANUAL"
    pnl_puntos: float = 0.0
    pnl_dinero: float = 0.0
    velas_en_operacion: int = 0
    max_favorable: float = 0.0  # Máximo precio favorable alcanzado
    max_adverso: float = 0.0   # Máximo precio adverso alcanzado
    
    def __post_init__(self):
        if self.id_operacion is None:
            self.id_operacion = f"OP_{self.timestamp_entrada.strftime('%Y%m%d_%H%M%S')}"


@dataclass
class ResultadoBacktest:
    """Resultados completos de un backtest."""
    # Configuración
    estrategia: str
    simbolo: str
    periodo_inicio: datetime
    periodo_fin: datetime
    timeframe_principal: str
    
    # Capital
    capital_inicial: float = 0.0
    capital_final: float = 0.0
    
    # Métricas principales
    total_operaciones: int = 0
    operaciones_totales: int = 0  # Alias para compatibilidad con tests
    operaciones_ganadoras: int = 0
    operaciones_perdedoras: int = 0
    operaciones_neutras: int = 0
    winrate: float = 0.0
    profit_factor: float = 0.0
    retorno_total: float = 0.0
    retorno_promedio: float = 0.0
    retorno_porcentual: float = 0.0  # Para compatibilidad con tests
    
    # Riesgo
    drawdown_maximo: float = 0.0
    drawdown_promedio: float = 0.0
    racha_ganadora_max: int = 0
    racha_perdedora_max: int = 0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    
    # Detalles
    operaciones: List[Operacion] = field(default_factory=list)
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list)
    metrics_extra: Dict[str, Any] = field(default_factory=dict)
    
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
            "winrate": round(self.winrate, 2),
            "profit_factor": round(self.profit_factor, 2),
            "retorno_total": round(self.retorno_total, 2),
            "retorno_promedio": round(self.retorno_promedio, 2),
            "drawdown_maximo": round(self.drawdown_maximo, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "racha_ganadora_max": self.racha_ganadora_max,
            "racha_perdedora_max": self.racha_perdedora_max,
            "metrics_extra": self.metrics_extra,
        }


class BacktestEngine:
    """
    Motor de backtesting que ejecuta estrategias sobre datos históricos.
    
    Características:
    - Replay barra a barra
    - Gestión de operaciones (TP, SL, expiración)
    - Cálculo de métricas profesionales
    - Equity curve
    - Soporte multi-timeframe
    """
    
    def __init__(
        self,
        estrategia: Estrategia,
        activo: ActivoInfo,
        capital_inicial: float = 10000.0,
        riesgo_por_operacion: float = 0.01,
        slippage_pips: float = 0.0,
        comision_lote: float = 0.0,
    ):
        """
        Inicializa el motor de backtest.
        
        Args:
            estrategia: Instancia de la estrategia a testear
            activo: Información del activo
            capital_inicial: Capital inicial
            riesgo_por_operacion: % del capital a arriesgar por operación
            slippage_pips: Slippage estimado en pips
            comision_lote: Comisión por lote
        """
        self.estrategia = estrategia
        self.activo = activo
        self.capital_inicial = capital_inicial
        self.riesgo_por_operacion = riesgo_por_operacion
        # Convertir pips a puntos (1 pip = 10 puntos para EURUSD)
        self.slippage_puntos = slippage_pips * activo.valor_pip * 10
        self.comision_puntos = comision_lote / activo.tamano_lote / activo.valor_pip / 10
        
        # Estado del backtest
        self.capital_actual = capital_inicial
        self.operaciones_abiertas: List[Operacion] = []
        self.operaciones_cerradas: List[Operacion] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.señales_generadas: List[Señal] = []
        
        # Contexto compartido
        self.contexto: Optional[Contexto] = None
    
    def _crear_contexto(self, feeds: Dict[str, CSVFeed]) -> Contexto:
        """Crea un contexto desde los feeds actuales."""
        ctx = Contexto(
            activo=self.activo,
            precio=0.0,
            tiempo=datetime.now(timezone.utc),
            point=self.activo.punto,
            broker_tz_offset=self.activo.timezone,
        )
        
        # Asignar DataFrames por timeframe
        for tf, feed in feeds.items():
            df_attr = f"df_{tf.lower()}"
            if hasattr(ctx, df_attr):
                setattr(ctx, df_attr, feed.get_bars(n=500))
        
        # Inyectar detectores del core si están disponibles
        try:
            from core.d0_estructura import EstructuraDetector
            from core.d5_mss_sweep import MSSDetector
            
            # Esto se mejorará en iteraciones futuras
            ctx.estructura = None
            ctx.mss_cache = None
        except ImportError:
            pass
        
        return ctx
    
    def _aplicar_slippage(self, precio: float, direccion: int) -> float:
        """Aplica slippage al precio de entrada."""
        ajuste = self.slippage_puntos * self.activo.punto
        if direccion == 1:  # LONG - entrar más caro
            return precio + ajuste
        else:  # SHORT - entrar más barato
            return precio - ajuste
    
    def _calcular_tamano_posicion(self, precio_entrada: float, stop_loss: float) -> float:
        """Calcula el tamaño de posición basado en el riesgo."""
        if stop_loss is None or precio_entrada == stop_loss:
            return 0.0
        
        riesgo_puntos = abs(precio_entrada - stop_loss) / self.activo.punto
        riesgo_dinero = self.capital_actual * self.riesgo_por_operacion
        
        if riesgo_puntos == 0:
            return 0.0
        
        lotes = riesgo_dinero / (riesgo_puntos * self.activo.punto * self.activo.contract_size)
        return round(lotes, 2)
    
    def _abrir_operacion(self, señal: Señal, precio_entrada: float) -> Operacion:
        """Abre una nueva operación."""
        op = Operacion(
            id_operacion=None,
            señal=señal,
            simbolo=señal.simbolo,
            direccion=señal.direccion,
            precio_entrada=precio_entrada,
            timestamp_entrada=señal.tiempo,
            stop_loss=señal.stop_loss,
            take_profit=señal.take_profit,
        )
        
        self.operaciones_abiertas.append(op)
        return op
    
    def _cerrar_operacion(
        self,
        operacion: Operacion,
        precio_salida: float,
        timestamp_salida: datetime,
        razon: str,
    ):
        """Cierra una operación y calcula PnL."""
        # Calcular PnL en puntos
        if operacion.direccion == 1:  # LONG
            pnl_puntos = (precio_salida - operacion.precio_entrada) / self.activo.punto
        else:  # SHORT
            pnl_puntos = (operacion.precio_entrada - precio_salida) / self.activo.punto
        
        # Restar comisión
        pnl_puntos -= self.comision_puntos * 2  # Entrada + salida
        
        # Calcular PnL en dinero
        operacion.pnl_dinero = pnl_puntos * self.activo.punto * self.activo.contract_size
        
        # Actualizar operación
        operacion.precio_salida = precio_salida
        operacion.timestamp_salida = timestamp_salida
        operacion.razon_salida = razon
        operacion.pnl_puntos = pnl_puntos
        
        # Mover a cerradas
        self.operaciones_abiertas.remove(operacion)
        self.operaciones_cerradas.append(operacion)
        
        # Actualar capital
        self.capital_actual += operacion.pnl_dinero
    
    def _gestionar_operaciones_abiertas(self, bar_actual: Dict[str, Any]):
        """Gestiona las operaciones abiertas contra la vela actual."""
        high = bar_actual["high"]
        low = bar_actual["low"]
        close = bar_actual["close"]
        timestamp = bar_actual["timestamp"]
        
        # Iterar sobre copia para poder modificar la lista original
        for operacion in self.operaciones_abiertas[:]:
            operacion.velas_en_operacion += 1
            
            # Actualizar máximos favorables/adversos
            if operacion.direccion == 1:  # LONG
                operacion.max_favorable = max(operacion.max_favorable, high)
                operacion.max_adverso = min(operacion.max_adverso, low)
                
                # Verificar TP
                if operacion.take_profit and high >= operacion.take_profit:
                    self._cerrar_operacion(operacion, operacion.take_profit, timestamp, "TP")
                    continue
                
                # Verificar SL
                if operacion.stop_loss and low <= operacion.stop_loss:
                    self._cerrar_operacion(operacion, operacion.stop_loss, timestamp, "SL")
                    continue
                
            else:  # SHORT
                operacion.max_favorable = min(operacion.max_favorable, low)
                operacion.max_adverso = max(operacion.max_adverso, high)
                
                # Verificar TP
                if operacion.take_profit and low <= operacion.take_profit:
                    self._cerrar_operacion(operacion, operacion.take_profit, timestamp, "TP")
                    continue
                
                # Verificar SL
                if operacion.stop_loss and high >= operacion.stop_loss:
                    self._cerrar_operacion(operacion, operacion.stop_loss, timestamp, "SL")
                    continue
            
            # Verificar expiración por velas
            if operacion.velas_en_operacion >= operacion.señal.expiracion_velas:
                self._cerrar_operacion(operacion, close, timestamp, "EXPIRED")
                continue
    
    def _calcular_metricas(self) -> ResultadoBacktest:
        """Calcula todas las métricas del backtest."""
        resultado = ResultadoBacktest(
            estrategia=self.estrategia.nombre,
            simbolo=self.activo.simbolo,
            periodo_inicio=self.equity_curve[0][0] if self.equity_curve else datetime(1970, 1, 1),
            periodo_fin=self.equity_curve[-1][0] if self.equity_curve else datetime(1970, 1, 1),
            timeframe_principal="M15",  # Debería venir de los feeds
            capital_inicial=self.capital_inicial,
            capital_final=self.capital_actual,
            operaciones=self.operaciones_cerradas,
            equity_curve=self.equity_curve,
        )
        
        if not self.operaciones_cerradas:
            return resultado
        
        # Contar ganadoras/perdedoras
        gains = [op.pnl_dinero for op in self.operaciones_cerradas if op.pnl_dinero > 0]
        losses = [op.pnl_dinero for op in self.operaciones_cerradas if op.pnl_dinero < 0]
        neutral = [op for op in self.operaciones_cerradas if op.pnl_dinero == 0]
        
        resultado.operaciones_ganadoras = len(gains)
        resultado.operaciones_perdedoras = len(losses)
        resultado.operaciones_neutras = len(neutral)
        resultado.total_operaciones = len(self.operaciones_cerradas)
        resultado.operaciones_totales = resultado.total_operaciones  # Alias
        
        # Winrate
        if resultado.total_operaciones > 0:
            resultado.winrate = (resultado.operaciones_ganadoras / resultado.total_operaciones) * 100
        
        # Profit Factor
        total_gains = sum(gains)
        total_losses = abs(sum(losses))
        if total_losses > 0:
            resultado.profit_factor = total_gains / total_losses
        elif total_gains > 0:
            resultado.profit_factor = float('inf')
        
        # Retorno
        resultado.retorno_total = ((self.capital_actual - self.capital_inicial) / self.capital_inicial) * 100
        resultado.retorno_promedio = resultado.retorno_total / resultado.total_operaciones if resultado.total_operaciones > 0 else 0
        resultado.retorno_porcentual = resultado.retorno_total  # Alias para tests
        
        # Drawdown
        if len(self.equity_curve) > 1:
            equity_values = [e[1] for e in self.equity_curve]
            peak = equity_values[0]
            drawdowns = []
            
            for value in equity_values:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak * 100 if peak > 0 else 0
                drawdowns.append(drawdown)
            
            resultado.drawdown_maximo = max(drawdowns)
            resultado.drawdown_promedio = sum(drawdowns) / len(drawdowns) if drawdowns else 0
        
        # Rachas
        current_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        last_result = None
        
        for op in self.operaciones_cerradas:
            if op.pnl_dinero > 0:
                if last_result == "win":
                    current_streak += 1
                else:
                    current_streak = 1
                last_result = "win"
                max_win_streak = max(max_win_streak, current_streak)
            elif op.pnl_dinero < 0:
                if last_result == "loss":
                    current_streak += 1
                else:
                    current_streak = 1
                last_result = "loss"
                max_loss_streak = max(max_loss_streak, current_streak)
            else:
                current_streak = 0
                last_result = None
        
        resultado.racha_ganadora_max = max_win_streak
        resultado.racha_perdedora_max = max_loss_streak
        
        # Sharpe Ratio (simplificado)
        if len(self.equity_curve) > 1:
            returns = []
            for i in range(1, len(self.equity_curve)):
                prev_eq = self.equity_curve[i-1][1]
                curr_eq = self.equity_curve[i][1]
                if prev_eq > 0:
                    returns.append((curr_eq - prev_eq) / prev_eq)
            
            if returns and np.std(returns) > 0:
                avg_return = np.mean(returns)
                std_return = np.std(returns)
                resultado.sharpe_ratio = (avg_return / std_return) * np.sqrt(252)  # Annualizado
                
                # Sortino Ratio (solo desviación negativa)
                downside_returns = [r for r in returns if r < 0]
                if downside_returns:
                    downside_std = np.std(downside_returns)
                    if downside_std > 0:
                        resultado.sortino_ratio = (avg_return / downside_std) * np.sqrt(252)
        
        return resultado
    
    def ejecutar(
        self,
        feeds: Dict[str, CSVFeed],
        params_estrategia: Optional[Dict[str, Any]] = None,
    ) -> ResultadoBacktest:
        """
        Ejecuta el backtest completo.
        
        Args:
            feeds: Diccionario {timeframe: CSVFeed} con los datos
            params_estrategia: Parámetros para la estrategia
            
        Returns:
            ResultadoBacktest con métricas completas
        """
        # Resetear estado
        self.capital_actual = self.capital_inicial
        self.operaciones_abiertas = []
        self.operaciones_cerradas = []
        self.equity_curve = []
        self.señales_generadas = []
        
        # Setup de la estrategia
        self.estrategia.setup(params_estrategia or {}, self.activo)
        
        # Obtener feed de referencia (el de menor timeframe)
        ref_timeframe = min(feeds.keys(), key=lambda tf: CSVFeed.TIMEFRAME_MAP.get(tf, 999999))
        ref_feed = feeds[ref_timeframe]
        
        # Iterar barra a barra
        for bar in ref_feed.iter_barras():
            # Actualizar contexto
            self.contexto = self._crear_contexto(feeds)
            self.contexto.precio = bar["close"]
            self.contexto.tiempo = bar["timestamp"]
            
            # Ejecutar estrategia
            señales = self.estrategia.detectar(self.contexto)
            
            # Procesar señales
            for señal in señales:
                señal.tiempo = bar["timestamp"]
                señal.precio = bar["close"]
                self.señales_generadas.append(señal)
                
                # Abrir operación si hay espacio
                if len(self.operaciones_abiertas) < 3:  # Máximo 3 operaciones simultáneas
                    precio_entrada = self._aplicar_slippage(bar["close"], señal.direccion)
                    self._abrir_operacion(señal, precio_entrada)
            
            # Gestionar operaciones abiertas
            self._gestionar_operaciones_abiertas(bar)
            
            # Registrar equity
            equity_actual = self.capital_actual + sum(
                self._calcular_equity_operacion(op, bar)
                for op in self.operaciones_abiertas
            )
            self.equity_curve.append((bar["timestamp"], equity_actual))
        
        # Calcular métricas finales
        return self._calcular_metricas()
    
    def _calcular_equity_operacion(self, operacion: Operacion, bar: Dict[str, Any]) -> float:
        """Calcula el equity flotante de una operación abierta."""
        close = bar["close"]
        
        if operacion.direccion == 1:  # LONG
            pnl_puntos = (close - operacion.precio_entrada) / self.activo.punto
        else:  # SHORT
            pnl_puntos = (operacion.precio_entrada - close) / self.activo.punto
        
        return pnl_puntos * self.activo.punto * self.activo.contract_size


def run_backtest(
    estrategia: Estrategia,
    activo: ActivoInfo,
    data_path: str,
    timeframe: str = "M15",
    params: Optional[Dict[str, Any]] = None,
    capital: float = 10000.0,
    riesgo: float = 0.01,
) -> ResultadoBacktest:
    """
    Función helper para ejecutar un backtest rápidamente.
    
    Args:
        estrategia: Instancia de estrategia
        activo: Información del activo
        data_path: Ruta al CSV con datos
        timeframe: Timeframe principal
        params: Parámetros para la estrategia
        capital: Capital inicial
        riesgo: Riesgo por operación
        
    Returns:
        ResultadoBacktest completo
    """
    # Crear feed
    feed = CSVFeed(path=data_path, timeframe=timeframe, symbol=activo.simbolo)
    
    # Crear engine
    engine = BacktestEngine(
        estrategia=estrategia,
        activo=activo,
        capital_inicial=capital,
        riesgo_por_operacion=riesgo,
    )
    
    # Ejecutar
    return engine.ejecutar(feeds={timeframe: feed}, params_estrategia=params)
