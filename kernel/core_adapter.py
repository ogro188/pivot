# -*- coding: utf-8 -*-
"""
Adaptador para integrar los detectores del Core (D0-D5) con el Kernel.
Permite usar la lógica existente de detectores en el nuevo sistema de backtesting.
"""
import pandas as pd
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from copy import deepcopy

# Importar tipos del kernel
from kernel.contrato import Contexto as KernelContexto, ActivoInfo
from core.base import Contexto as CoreContexto
from core.d0_estructura import EstructuraProvider
from core.estructuras import EstructuraRef


class CoreAdapter:
    """
    Adapta el Contexto del Kernel al formato esperado por los detectores del Core.
    Permite reutilizar toda la lógica de detectores D0-D5 existentes.
    """
    
    def __init__(self):
        self.core_ctx: Optional[CoreContexto] = None
        self.estructura_provider: Optional[EstructuraProvider] = None
    
    def adaptar_contexto(self, kernel_ctx: KernelContexto) -> CoreContexto:
        """
        Convierte un Contexto del Kernel al formato del Core.
        
        Args:
            kernel_ctx: Contexto desde el kernel con dataframes y estado
            
        Returns:
            Contexto compatible con los detectores del core
        """
        # Crear contexto del core
        core_ctx = CoreContexto()
        
        # Copiar DataFrames (mapeo de timeframes)
        core_ctx.df_m15 = kernel_ctx.df_m15
        core_ctx.df_h1 = kernel_ctx.df_h1
        core_ctx.df_h4 = kernel_ctx.df_h4
        core_ctx.df_d1 = kernel_ctx.df_d1
        
        # Copiar buffers de indicadores
        core_ctx.g_atr8_buffer = kernel_ctx.g_atr8_buffer.copy()
        core_ctx.g_atr14_buffer = kernel_ctx.g_atr14_buffer.copy()
        core_ctx.g_atr30_buffer = kernel_ctx.g_atr30_buffer.copy()
        core_ctx.g_ema21_buffer = kernel_ctx.g_ema21_buffer.copy()
        core_ctx.g_ema50_buffer = kernel_ctx.g_ema50_buffer.copy()
        core_ctx.g_rsi14_buffer = kernel_ctx.g_rsi14_buffer.copy()
        core_ctx.g_ema50_d1_buffer = kernel_ctx.g_ema50_d1_buffer.copy()
        core_ctx.g_ema200_d1_buffer = kernel_ctx.g_ema200_d1_buffer.copy()
        core_ctx.g_ema20_h4_buffer = kernel_ctx.g_ema20_h4_buffer.copy()
        core_ctx.g_ema50_h4_buffer = kernel_ctx.g_ema50_h4_buffer.copy()
        
        # Copiar métricas G
        core_ctx.g1 = kernel_ctx.g1
        core_ctx.g2 = kernel_ctx.g2
        core_ctx.g3 = kernel_ctx.g3
        core_ctx.g4 = kernel_ctx.g4
        
        # Copiar contexto temporal
        core_ctx.session = kernel_ctx.session
        core_ctx.kill_zone = kernel_ctx.kill_zone
        core_ctx.trend_d1 = kernel_ctx.trend_d1
        core_ctx.regimen_vol = kernel_ctx.regimen_vol
        
        # Copiar parámetros
        core_ctx.point = kernel_ctx.point
        core_ctx.broker_tz_offset = kernel_ctx.broker_tz_offset
        
        # Copiar funciones helper
        core_ctx.get_volume_ratio_cached = kernel_ctx.get_volume_ratio_cached
        core_ctx.get_volume_ratio = kernel_ctx.get_volume_ratio
        core_ctx.detect_mss_h4 = kernel_ctx.detect_mss_h4
        core_ctx.es_zona_premium_discount = kernel_ctx.es_zona_premium_discount
        core_ctx.evaluar_contexto_estructural = kernel_ctx.evaluar_contexto_estructural
        
        # Actualizar estructura usando D0
        if core_ctx.df_h1 is not None and len(core_ctx.df_h1) > 50:
            self.estructura_provider = EstructuraProvider(core_ctx)
            estructura = self.estructura_provider.actualizar()
            core_ctx.estructura = estructura
        
        self.core_ctx = core_ctx
        return core_ctx
    
    def obtener_estructura(self) -> Optional[EstructuraRef]:
        """Obtiene la estructura actual calculada por D0."""
        if self.core_ctx and self.core_ctx.estructura:
            return self.core_ctx.estructura
        return None
    
    def ejecutar_detectores(self, detectores: List[Any]) -> Dict[str, Any]:
        """
        Ejecuta una lista de detectores sobre el contexto actual.
        
        Args:
            detectores: Lista de instancias de detectores (D1, D2, D3, etc.)
            
        Returns:
            Diccionario con resultados por detector
        """
        if not self.core_ctx:
            raise ValueError("Debe llamar a adaptar_contexto() primero")
        
        resultados = {}
        for detector in detectores:
            try:
                señal = detector.detectar(self.core_ctx)
                if señal:
                    clasificacion = detector.clasificar(señal, self.core_ctx)
                    resultados[detector.nombre] = {
                        "senal": señal,
                        "clasificacion": clasificacion,
                        "nombre": detector.nombre
                    }
            except Exception as e:
                resultados[detector.nombre] = {"error": str(e)}
        
        return resultados


def calcular_indicadores_core(df: pd.DataFrame) -> Dict[str, List[float]]:
    """
    Calcula todos los indicadores necesarios para los detectores del core.
    
    Args:
        df: DataFrame con columnas open, high, low, close, tick_volume
        
    Returns:
        Diccionario con buffers de indicadores (índice 0 = más reciente)
    """
    if df is None or len(df) == 0:
        return {}
    
    # Calcular ATRs
    high = df['high']
    low = df['low']
    close = df['close']
    close_prev = close.shift(1)
    
    tr = pd.concat([
        high - low,
        (high - close_prev).abs(),
        (low - close_prev).abs()
    ], axis=1).max(axis=1)
    
    atr8 = tr.ewm(span=8, adjust=False).mean()
    atr14 = tr.ewm(span=14, adjust=False).mean()
    atr30 = tr.ewm(span=30, adjust=False).mean()
    
    # Calcular EMAs
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    
    # Calcular RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi14 = 100 - (100 / (1 + rs))
    
    # Convertir a buffers (índice 0 = último valor)
    def to_buffer(series: pd.Series) -> List[float]:
        return [float(x) if not pd.isna(x) else 0.0 for x in series.iloc[::-1].values]
    
    return {
        'g_atr8_buffer': to_buffer(atr8),
        'g_atr14_buffer': to_buffer(atr14),
        'g_atr30_buffer': to_buffer(atr30),
        'g_ema21_buffer': to_buffer(ema21),
        'g_ema50_buffer': to_buffer(ema50),
        'g_rsi14_buffer': to_buffer(rsi14),
    }


def actualizar_contexto_con_indicadores(ctx: KernelContexto, timeframe: str = "M15"):
    """
    Actualiza los buffers de indicadores del contexto usando los dataframes disponibles.
    
    Args:
        ctx: Contexto del kernel a actualizar
        timeframe: Timeframe principal para calcular indicadores
    """
    df = getattr(ctx, f"df_{timeframe.lower()}", None)
    if df is None or len(df) == 0:
        return
    
    # Calcular indicadores
    indicadores = calcular_indicadores_core(df)
    
    # Actualizar buffers
    for key, value in indicadores.items():
        if hasattr(ctx, key):
            setattr(ctx, key, value)
    
    # Calcular métricas G básicas
    if len(indicadores.get('g_atr8_buffer', [])) > 0 and len(indicadores.get('g_atr14_buffer', [])) > 0:
        ctx.g1 = indicadores['g_atr8_buffer'][0] / indicadores['g_atr14_buffer'][0] if indicadores['g_atr14_buffer'][0] > 0 else 1.0
    
    # Volume ratio (simplificado)
    if 'tick_volume' in df.columns and len(df) > 20:
        vol_actual = df['tick_volume'].iloc[-1]
        vol_promedio = df['tick_volume'].iloc[-21:-1].mean()
        ctx.g2 = vol_actual / vol_promedio if vol_promedio > 0 else 1.0
    
    # Trend strength (basado en EMA)
    if len(indicadores.get('g_ema21_buffer', [])) > 0 and len(indicadores.get('g_ema50_buffer', [])) > 0:
        ema21 = indicadores['g_ema21_buffer'][0]
        ema50 = indicadores['g_ema50_buffer'][0]
        if ema50 > 0:
            ctx.g3 = abs(ema21 - ema50) / ema50
        else:
            ctx.g3 = 0.0
    
    # Volatility regime (basado en ATR)
    if len(indicadores.get('g_atr14_buffer', [])) > 10:
        atr_reciente = indicadores['g_atr14_buffer'][0]
        atr_promedio = sum(indicadores['g_atr14_buffer'][:10]) / 10
        ctx.g4 = atr_reciente / atr_promedio if atr_promedio > 0 else 1.0
