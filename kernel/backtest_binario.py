# -*- coding: utf-8 -*-
"""
Kernel de PIVOT - Motor de Backtesting para Opciones Binarias.
Ejecuta estrategias sobre datos históricos y calcula métricas específicas para binarias.

Diferencias clave vs backtest tradicional:
- No hay SL/TP, el resultado se evalúa al tiempo fijo de expiración
- El payout del broker determina la ganancia (ej: 80%)
- La pérdida es total si se falla (-100%)
- Se soportan operaciones simultáneas con diferentes tiempos de expiración
"""
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from copy import deepcopy

from kernel.contrato_binario import (
    SeñalBinaria, OperacionBinaria, ResultadoBacktestBinario,
    ConfiguracionBinaria, TipoOpcion, EstrategiaBinaria
)
from kernel.contrato import Contexto, ActivoInfo
from kernel.feeds.csv import CSVFeed


class BacktestEngineBinario:
    """
    Motor de backtesting especializado en opciones binarias.
    
    Características:
    - Replay barra a barra con evaluación en tiempo de expiración
    - Soporte para múltiples operaciones simultáneas con diferentes expiraciones
    - Cálculo de métricas específicas: Win Rate, Expectativa Matemática, Profit Factor
    - Análisis por tipo de detector, sesión y tiempo de expiración
    - Curva de capital (equity curve)
    """
    
    def __init__(
        self,
        estrategia: EstrategiaBinaria,
        activo: ActivoInfo,
        config_binaria: ConfiguracionBinaria,
        capital_inicial: float = 1000.0,
        db: Any = None,
    ):
        """
        Inicializa el motor de backtest binario.
        
        Args:
            estrategia: Instancia de la estrategia binaria
            activo: Información del activo
            config_binaria: Configuración específica para binarias
            capital_inicial: Capital inicial (ej: $1000)
            db: Instancia de Database para persistencia (opcional)
        """
        self.estrategia = estrategia
        self.activo = activo
        self.config = config_binaria
        self.capital_inicial = capital_inicial
        self.db = db
        
        # Estado del backtest
        self.capital_actual = capital_inicial
        self.operaciones_abiertas: List[OperacionBinaria] = []
        self.operaciones_cerradas: List[OperacionBinaria] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.señales_generadas: List[SeñalBinaria] = []
        
        # Contadores para martingale
        self.racha_actual = 0
        self.nivel_martingale = 0
        self.last_resultado = None
        
        # Contexto compartido
        self.contexto: Optional[Contexto] = None
    
    def _crear_contexto(self, feeds: Dict[str, CSVFeed]) -> Contexto:
        """Crea un contexto desde los feeds actuales."""
        from kernel.feeds.csv_resample import resamplear_ohlc
        
        ctx = Contexto(
            activo=self.activo,
            precio=0.0,
            tiempo=datetime.now(timezone.utc),
            point=self.activo.punto,
            broker_tz_offset=self.activo.timezone,
        )
        
        # Obtener feed base para resampling
        tf_base = min(feeds.keys(), key=lambda tf: 
            {"M1":1, "M3":3, "M5":5, "M15":15, "M30":30, "H1":60, "H4":240, "D1":1440}.get(tf, 9999))
        df_base = feeds[tf_base].df
        
        # Generar timeframes requeridos
        timeframes_requeridos = getattr(self.estrategia, "timeframes", ["M15", "H1", "H4", "D1"])
        
        for tf in timeframes_requeridos:
            df_attr = f"df_{tf.lower()}"
            if not hasattr(ctx, df_attr):
                continue
            
            if tf in feeds:
                setattr(ctx, df_attr, feeds[tf].get_bars(n=500) if feeds[tf].idx > 0 else feeds[tf].df.tail(500))
            elif tf in ["H1", "H4", "D1"]:
                try:
                    if hasattr(self, '_precalc') and tf in self._precalc:
                        df_resampled = self._precalc[tf].tail(500)
                    else:
                        df_resampled = resamplear_ohlc(df_base, tf).tail(500)
                    setattr(ctx, df_attr, df_resampled)
                except Exception:
                    pass
        
        return ctx
    
    def _calcular_capital_apuesta(self, operacion_previa: Optional[OperacionBinaria] = None) -> float:
        """
        Calcula el capital a apostar considerando martingale opcional.
        
        Args:
            operacion_previa: Operación anterior para calcular martingale
            
        Returns:
            Capital a apostar en esta operación
        """
        capital_base = self.capital_actual * self.config.porcentaje_riesgo
        
        if not self.config.usar_martingale or operacion_previa is None:
            return capital_base
        
        # Aplicar martingale si hubo pérdida
        if operacion_previa.resultado == "LOSS" and self.nivel_martingale < self.config.martingale_max_nivel:
            self.nivel_martingale += 1
            multiplicador = self.config.martingale_multiplicador ** self.nivel_martingale
            return capital_base * multiplicador
        else:
            # Resetear martingale después de win o máximo nivel
            self.nivel_martingale = 0
            return capital_base
    
    def _abrir_operacion(self, señal: SeñalBinaria, capital_arriesgado: float) -> OperacionBinaria:
        """Abre una nueva operación binaria."""
        op = OperacionBinaria(
            id_operacion=None,
            señal=señal,
            simbolo=señal.simbolo,
            tipo_opcion=señal.tipo_opcion,
            precio_entrada=señal.precio_entrada,
            timestamp_entrada=señal.tiempo_entrada,
            expiracion_minutos=señal.expiracion_minutos,
            timestamp_expiracion=señal.tiempo_expiracion,
            capital_arriesgado=capital_arriesgado,
            payout_esperado=self.config.payout_call if señal.tipo_opcion == TipoOpcion.CALL else self.config.payout_put,
        )
        
        self.operaciones_abiertas.append(op)
        self.señales_generadas.append(señal)
        return op
    
    def _cerrar_operacion(
        self,
        operacion: OperacionBinaria,
        precio_expiracion: float,
        timestamp_expiracion: datetime,
    ):
        """Cierra una operación y calcula el PnL basado en el resultado."""
        # Evaluar resultado
        resultado = operacion.señal.evaluar_resultado(precio_expiracion)
        
        # Calcular PnL porcentual
        pnl_porcentual = operacion.señal.calcular_pnl(resultado, operacion.payout_esperado)
        
        # Calcular PnL en dinero
        pnl_dinero = operacion.capital_arriesgado * (pnl_porcentual / 100.0)
        
        # Actualizar operación
        operacion.precio_expiracion = precio_expiracion
        operacion.timestamp_expiracion = timestamp_expiracion
        operacion.resultado = resultado
        operacion.pnl_porcentual = pnl_porcentual
        operacion.pnl_dinero = pnl_dinero
        
        # Mover a cerradas
        self.operaciones_abiertas.remove(operacion)
        self.operaciones_cerradas.append(operacion)
        
        # Actualizar capital
        self.capital_actual += pnl_dinero
        
        # Actualizar racha para martingale
        if resultado == "WIN":
            self.racha_actual = max(0, self.racha_actual + 1)
            self.last_resultado = "WIN"
        elif resultado == "LOSS":
            self.racha_actual = -(abs(self.racha_actual) + 1) if self.racha_actual < 0 else -1
            self.last_resultado = "LOSS"
        else:  # ATM
            self.last_resultado = "ATM"
        
        # Registrar en dataset ML si hay DB
        if self.db is not None:
            try:
                detectores = operacion.señal.detectores_activos
                self.db.guardar_resultado_operacion({
                    "timestamp_entrada": operacion.timestamp_entrada.isoformat(),
                    "timestamp_salida": operacion.timestamp_expiracion.isoformat(),
                    "simbolo": operacion.simbolo,
                    "direccion": operacion.señal.direccion_int,
                    "detectores_activos": detectores,
                    "pnl_puntos": pnl_porcentual,
                    "razon_salida": resultado,
                    "fue_ganadora": resultado == "WIN",
                    "pnl_dinero": pnl_dinero,
                    "expiracion_minutos": operacion.expiracion_minutos,
                    "session": operacion.señal.session,
                })
            except Exception as e:
                print(f"[BacktestBinario] Error persistiendo operación ML: {e}")
    
    def _gestionar_operaciones_abiertas(self, bar_actual: Dict[str, Any]):
        """Gestiona las operaciones abiertas verificando si han expirado."""
        timestamp_barra = bar_actual["timestamp"]
        close = bar_actual["close"]
        
        # Iterar sobre copia para poder modificar la lista original
        for operacion in self.operaciones_abiertas[:]:
            operacion.velas_en_operacion += 1
            
            # Verificar si llegó el momento de expiración
            if timestamp_barra >= operacion.timestamp_expiracion:
                self._cerrar_operacion(operacion, close, timestamp_barra)
    
    def _calcular_metricas(self) -> ResultadoBacktestBinario:
        """Calcula todas las métricas del backtest binario."""
        resultado = ResultadoBacktestBinario(
            estrategia=self.estrategia.nombre,
            simbolo=self.activo.simbolo,
            periodo_inicio=self.equity_curve[0][0] if self.equity_curve else datetime(1970, 1, 1),
            periodo_fin=self.equity_curve[-1][0] if self.equity_curve else datetime(1970, 1, 1),
            timeframe_principal="M15",
            capital_inicial=self.capital_inicial,
            capital_final=self.capital_actual,
            operaciones=self.operaciones_cerradas,
            equity_curve=self.equity_curve,
        )
        
        if not self.operaciones_cerradas:
            return resultado
        
        # Contar resultados
        wins = [op for op in self.operaciones_cerradas if op.resultado == "WIN"]
        losses = [op for op in self.operaciones_cerradas if op.resultado == "LOSS"]
        atm = [op for op in self.operaciones_cerradas if op.resultado == "ATM"]
        
        resultado.operaciones_ganadoras = len(wins)
        resultado.operaciones_perdedoras = len(losses)
        resultado.operaciones_empate = len(atm)
        resultado.total_operaciones = len(self.operaciones_cerradas)
        
        # Win Rate
        if resultado.total_operaciones > 0:
            resultado.winrate = (resultado.operaciones_ganadoras / resultado.total_operaciones) * 100
        
        # Profit Factor (Ganancias totales / Pérdidas totales)
        total_gains = sum(op.pnl_dinero for op in wins)
        total_losses = abs(sum(op.pnl_dinero for op in losses))
        if total_losses > 0:
            resultado.profit_factor = total_gains / total_losses
        elif total_gains > 0:
            resultado.profit_factor = float('inf')
        
        # Retorno total y promedio
        resultado.retorno_total = ((self.capital_actual - self.capital_inicial) / self.capital_inicial) * 100
        resultado.retorno_promedio = resultado.retorno_total / resultado.total_operaciones if resultado.total_operaciones > 0 else 0
        
        # Expectativa Matemática (Valor esperado por operación)
        pnl_promedio = sum(op.pnl_dinero for op in self.operaciones_cerradas) / resultado.total_operaciones
        riesgo_promedio = sum(op.capital_arriesgado for op in self.operaciones_cerradas) / resultado.total_operaciones
        if riesgo_promedio > 0:
            resultado.expectativa_matematica = (pnl_promedio / riesgo_promedio) * 100
        
        # Rachas máximas
        racha_ganadora = 0
        racha_perdedora = 0
        racha_ganadora_max = 0
        racha_perdedora_max = 0
        
        for op in self.operaciones_cerradas:
            if op.resultado == "WIN":
                racha_ganadora += 1
                racha_perdedora = 0
                racha_ganadora_max = max(racha_ganadora_max, racha_ganadora)
            elif op.resultado == "LOSS":
                racha_perdedora += 1
                racha_ganadora = 0
                racha_perdedora_max = max(racha_perdedora_max, racha_perdedora)
            else:
                racha_ganadora = 0
                racha_perdedora = 0
        
        resultado.racha_ganadora_max = racha_ganadora_max
        resultado.racha_perdedora_max = racha_perdedora_max
        
        # Drawdown máximo
        if len(self.equity_curve) > 1:
            equity_values = [e[1] for e in self.equity_curve]
            peak = equity_values[0]
            drawdowns = []
            
            for value in equity_values:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak * 100 if peak > 0 else 0
                drawdowns.append(drawdown)
            
            resultado.drawdown_maximo = max(drawdowns) if drawdowns else 0
        
        # Sharpe Ratio (simplificado)
        if len(self.operaciones_cerradas) > 1:
            pnls = [op.pnl_porcentual for op in self.operaciones_cerradas]
            mean_pnl = np.mean(pnls)
            std_pnl = np.std(pnls)
            if std_pnl > 0:
                resultado.sharpe_ratio = (mean_pnl / std_pnl) * np.sqrt(252)  # Anualizado
        
        # Estadísticas por detector
        detectores_stats = {}
        for op in self.operaciones_cerradas:
            for detector in op.señal.detectores_activos:
                if detector not in detectores_stats:
                    detectores_stats[detector] = {
                        "total": 0, "wins": 0, "losses": 0, "winrate": 0.0,
                        "pnl_total": 0.0, "pnl_promedio": 0.0
                    }
                detectores_stats[detector]["total"] += 1
                if op.resultado == "WIN":
                    detectores_stats[detector]["wins"] += 1
                elif op.resultado == "LOSS":
                    detectores_stats[detector]["losses"] += 1
                detectores_stats[detector]["pnl_total"] += op.pnl_dinero
        
        # Calcular winrates y promedios por detector
        for detector, stats in detectores_stats.items():
            if stats["total"] > 0:
                stats["winrate"] = (stats["wins"] / stats["total"]) * 100
                stats["pnl_promedio"] = stats["pnl_total"] / stats["total"]
        
        resultado.estadisticas_por_detector = detectores_stats
        
        # Estadísticas por tiempo de expiración
        expiracion_stats = {}
        for op in self.operaciones_cerradas:
            exp = op.expiracion_minutos
            if exp not in expiracion_stats:
                expiracion_stats[exp] = {
                    "total": 0, "wins": 0, "losses": 0, "winrate": 0.0,
                    "pnl_total": 0.0
                }
            expiracion_stats[exp]["total"] += 1
            if op.resultado == "WIN":
                expiracion_stats[exp]["wins"] += 1
            elif op.resultado == "LOSS":
                expiracion_stats[exp]["losses"] += 1
            expiracion_stats[exp]["pnl_total"] += op.pnl_dinero
        
        for exp, stats in expiracion_stats.items():
            if stats["total"] > 0:
                stats["winrate"] = (stats["wins"] / stats["total"]) * 100
        
        resultado.estadisticas_por_expiracion = expiracion_stats
        
        # Estadísticas por sesión
        sesion_stats = {}
        for op in self.operaciones_cerradas:
            sesion = op.señal.session or "UNKNOWN"
            if sesion not in sesion_stats:
                sesion_stats[sesion] = {
                    "total": 0, "wins": 0, "losses": 0, "winrate": 0.0,
                    "pnl_total": 0.0
                }
            sesion_stats[sesion]["total"] += 1
            if op.resultado == "WIN":
                sesion_stats[sesion]["wins"] += 1
            elif op.resultado == "LOSS":
                sesion_stats[sesion]["losses"] += 1
            sesion_stats[sesion]["pnl_total"] += op.pnl_dinero
        
        for sesion, stats in sesion_stats.items():
            if stats["total"] > 0:
                stats["winrate"] = (stats["wins"] / stats["total"]) * 100
        
        resultado.estadisticas_por_sesion = sesion_stats
        
        return resultado
    
    def ejecutar(self, feeds: Dict[str, CSVFeed]) -> ResultadoBacktestBinario:
        """
        Ejecuta el backtest completo.
        
        Args:
            feeds: Diccionario de feeds por timeframe
            
        Returns:
            Resultados del backtest
        """
        print(f"[BacktestBinario] Iniciando backtest de {self.estrategia.nombre} en {self.activo.simbolo}...")
        
        # Setup inicial
        params = {k: v.get("default") if isinstance(v, dict) else v 
                  for k, v in getattr(self.estrategia, 'parametros', {}).items()}
        self.estrategia.setup(params, self.activo, self.config)
        
        # Crear contexto inicial
        self.contexto = self._crear_contexto(feeds)
        
        # Obtener timeframe principal
        tf_principal = "M15"
        if tf_principal not in feeds:
            raise ValueError(f"Feed {tf_principal} no disponible")
        
        feed_principal = feeds[tf_principal]
        
        # Resetear estado
        self.capital_actual = self.capital_inicial
        self.operaciones_abiertas = []
        self.operaciones_cerradas = []
        self.equity_curve = []
        self.señales_generadas = []
        
        # Loop principal de backtest
        print(f"[BacktestBinario] Procesando {len(feed_principal.df)} barras...")
        
        for idx in range(len(feed_principal.df)):
            # Avanzar feed
            feed_principal.idx = idx
            
            # Obtener barra actual
            barra = feed_principal.get_bars(n=1)
            if barra is None or len(barra) == 0:
                continue
            
            bar_actual = {
                "timestamp": barra.index[-1],
                "open": float(barra.iloc[-1]["open"]),
                "high": float(barra.iloc[-1]["high"]),
                "low": float(barra.iloc[-1]["low"]),
                "close": float(barra.iloc[-1]["close"]),
                "volume": int(barra.iloc[-1]["tick_volume"]) if "tick_volume" in barra.columns else int(barra.iloc[-1].get("volume", 0)),
            }
            
            # Actualizar contexto
            self.contexto = self._crear_contexto(feeds)
            self.contexto.precio = bar_actual["close"]
            self.contexto.tiempo = bar_actual["timestamp"]
            
            # Gestionar operaciones abiertas (verificar expiraciones)
            self._gestionar_operaciones_abiertas(bar_actual)
            
            # Generar señales
            try:
                señales = self.estrategia.detectar(self.contexto)
                
                # Abrir operaciones si hay señales y capacidad
                for señal in señales:
                    if len(self.operaciones_abiertas) >= 5:  # Máximo 5 operaciones simultáneas
                        break
                    
                    # Filtrar por volatilidad si está configurado
                    if not self.estrategia.filtrar_por_volatilidad(self.contexto, self.config):
                        continue
                    
                    # Calcular capital de apuesta
                    operacion_previa = self.operaciones_cerradas[-1] if self.operaciones_cerradas else None
                    capital_apuesta = self._calcular_capital_apuesta(operacion_previa)
                    
                    # Verificar capital suficiente
                    if capital_apuesta > self.capital_actual * 0.5:  # Máximo 50% del capital en una operación
                        continue
                    
                    self._abrir_operacion(señal, capital_apuesta)
                    
            except Exception as e:
                print(f"[BacktestBinario] Error en barra {idx}: {e}")
                continue
            
            # Registrar equity curve cada 10 barras o al final
            if idx % 10 == 0 or idx == len(feed_principal.df) - 1:
                self.equity_curve.append((bar_actual["timestamp"], self.capital_actual))
        
        # Calcular métricas finales
        print("[BacktestBinario] Calculando métricas finales...")
        resultados = self._calcular_metricas()
        
        print(f"\n{'='*60}")
        print(f"RESULTADOS BACKTEST BINARIO - {self.estrategia.nombre}")
        print(f"{'='*60}")
        print(f"Capital Inicial: ${resultados.capital_inicial:.2f}")
        print(f"Capital Final:   ${resultados.capital_final:.2f}")
        print(f"Retorno Total:   {resultados.retorno_total:.2f}%")
        print(f"Operaciones:     {resultados.total_operaciones}")
        print(f"Ganadoras:       {resultados.operaciones_ganadoras} ({resultados.winrate:.1f}%)")
        print(f"Perdedoras:      {resultados.operaciones_perdedoras}")
        print(f"Empate (ATM):    {resultados.operaciones_empate}")
        print(f"Profit Factor:   {resultados.profit_factor:.2f}")
        print(f"Expectativa Mat: {resultados.expectativa_matematica:.2f}%")
        print(f"Drawdown Max:    {resultados.drawdown_maximo:.2f}%")
        print(f"Racha Max Win:   {resultados.racha_ganadora_max}")
        print(f"Racha Max Loss:  {resultados.racha_perdedora_max}")
        print(f"{'='*60}\n")
        
        return resultados
