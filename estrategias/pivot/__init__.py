# -*- coding: utf-8 -*-
"""
Estrategia PIVOT - Estrategia principal basada en detectores D0-D5.
Combina estructura, rupturas, sweeps, FVGs, order blocks y MSS para generar señales de alta confianza.
"""
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from kernel.contrato import Estrategia, Contexto, Señal, ActivoInfo, Overlay
from kernel.core_adapter import CoreAdapter, actualizar_contexto_con_indicadores

# Importar detectores del core
from core.d1_ruptura import DetectorD1
from core.d2_sweep import DetectorD2
from core.d2_anticipacion import DetectorD2Anticipacion
from core.d3_fvg import DetectorD3
from core.d4_orderblock import DetectorD4
from core.d5_mss_sweep import DetectorD5


@dataclass
class ConfiguracionPivot:
    """Configuración de la estrategia Pivot."""
    # Profundidad de pivots
    pivot_depth: int = 2
    pivot_lookback: int = 24
    
    # Umbrales de ruptura
    n_ruptura: int = 4
    d1_atr_threshold: float = 0.50
    body_ratio_min: float = 0.40
    use_retest: bool = True
    use_volume: bool = True
    min_volume: float = 1.2
    
    # Sweeps
    sweep_n: int = 6
    sweep_wick_min: float = 0.55
    reclaim_body_min: float = 0.55
    
    # FVG
    fvg_min_size_atr: float = 0.20
    fvg_body_ratio: float = 0.55
    fvg_mitig_umbral: float = 0.50
    
    # Order Blocks
    ob_lookback: int = 12
    ob_body_min: float = 0.40
    ob_impulse_min: float = 0.70
    
    # MSS
    mss_lookback_h4: int = 20
    mss_max_age_h4_bars: int = 12
    
    # Gestión de riesgo
    risk_por_operacion: float = 1.0  # % del capital
    reward_ratio_min: float = 1.5    # R:R mínimo
    expiracion_velas: int = 4
    
    # Filtros de contexto
    usar_kill_zones: bool = True
    usar_trend_d1: bool = True
    confianza_minima: float = 60.0


class EstrategiaPivot(Estrategia):
    """
    Estrategia PIVOT principal.
    
    Combina todos los detectores D0-D5 para identificar setups de alta probabilidad:
    - D0: Estructura de mercado (pivots, zona de interés)
    - D1: Rupturas de rango con volumen
    - D2: Sweeps de liquidez con reclaim
    - D3: Fair Value Gaps (FVG)
    - D4: Order Blocks institucionales
    - D5: MSS (Market Structure Shift) con sweep
    
    Reglas de entrada:
    1. Alineación con tendencia D1 (opcional)
    2. Sweep de liquidez en zona premium/discount
    3. Ruptura estructural (MSS) confirmada
    4. Entrada en FVG o Order Block
    5. Stop Loss detrás del swing
    6. Take Profit en siguiente zona de liquidez
    """
    
    nombre = "PIVOT"
    version = "1.0.0"
    timeframes = ["M15", "H1", "H4", "D1"]
    eventos = ["candle_close"]
    
    parametros = {
        "pivot_depth": {"tipo": "int", "default": 2, "min": 1, "max": 5, "descripcion": "Profundidad del pivot"},
        "pivot_lookback": {"tipo": "int", "default": 24, "min": 10, "max": 50, "descripcion": "Ventana de búsqueda"},
        "n_ruptura": {"tipo": "int", "default": 4, "min": 2, "max": 10},
        "d1_atr_threshold": {"tipo": "float", "default": 0.50, "min": 0.1, "max": 2.0},
        "risk_por_operacion": {"tipo": "float", "default": 1.0, "min": 0.1, "max": 5.0},
        "reward_ratio_min": {"tipo": "float", "default": 1.5, "min": 1.0, "max": 5.0},
        "confianza_minima": {"tipo": "float", "default": 60.0, "min": 40.0, "max": 90.0},
        "usar_kill_zones": {"tipo": "bool", "default": True},
        "usar_trend_d1": {"tipo": "bool", "default": True},
    }
    
    def __init__(self):
        self.config: Optional[ConfiguracionPivot] = None
        self.adapter: Optional[CoreAdapter] = None
        self.activo_info: Optional[ActivoInfo] = None
        
        # Instanciar detectores
        self.detectores = {
            "D1": DetectorD1(),
            "D2": DetectorD2(),
            "D2Ant": DetectorD2Anticipacion(),
            "D3": DetectorD3(),
            "D4": DetectorD4(),
            "D5": DetectorD5(),
        }
    
    def setup(self, params: Dict[str, Any], activo: ActivoInfo) -> None:
        """Inicializa la estrategia con parámetros configurados."""
        self.activo_info = activo
        
        # Crear configuración desde parámetros
        self.config = ConfiguracionPivot(
            pivot_depth=params.get("pivot_depth", 2),
            pivot_lookback=params.get("pivot_lookback", 24),
            n_ruptura=params.get("n_ruptura", 4),
            d1_atr_threshold=params.get("d1_atr_threshold", 0.50),
            risk_por_operacion=params.get("risk_por_operacion", 1.0),
            reward_ratio_min=params.get("reward_ratio_min", 1.5),
            confianza_minima=params.get("confianza_minima", 60.0),
            usar_kill_zones=params.get("usar_kill_zones", True),
            usar_trend_d1=params.get("usar_trend_d1", True),
        )
        
        # Inicializar adaptador
        self.adapter = CoreAdapter()
        
        # Actualizar parámetros en detectores (se hará en cada iteración del backtest)
    
    def detectar(self, ctx: Contexto) -> List[Señal]:
        """
        Evalúa el contexto actual y genera señales de trading.
        
        Flujo:
        1. Actualizar indicadores y métricas G
        2. Adaptar contexto al formato del core
        3. Ejecutar detectores D0-D5
        4. Combinar señales y calcular confianza
        5. Generar señal final con gestión de riesgo
        """
        if not self.config or not self.adapter:
            return []
        
        # Actualizar indicadores
        actualizar_contexto_con_indicadores(ctx, "M15")
        
        # Adaptar contexto
        try:
            core_ctx = self.adapter.adaptar_contexto(ctx)
        except Exception as e:
            print(f"[PIVOT] Error adaptando contexto: {e}")
            return []
        
        # Aplicar parámetros al contexto
        core_ctx.inp_pivot_depth = self.config.pivot_depth
        core_ctx.inp_pivot_lookback = self.config.pivot_lookback
        core_ctx.inp_n_ruptura = self.config.n_ruptura
        core_ctx.inp_d1_atr_threshold = self.config.d1_atr_threshold
        core_ctx.inp_sweep_n = self.config.sweep_n
        core_ctx.inp_fvg_min_size_atr = self.config.fvg_min_size_atr
        core_ctx.inp_ob_lookback = self.config.ob_lookback
        
        # Obtener estructura (D0)
        estructura = self.adapter.obtener_estructura()
        if not estructura or not estructura.valida:
            return []
        
        # Ejecutar detectores
        resultados = self.adapter.ejecutar_detectores(list(self.detectores.values()))
        
        # Filtrar detectores con señales válidas
        detectores_activos = [k for k, v in resultados.items() if "senal" in v and v.get("clasificacion") in ["A", "B"]]
        
        if len(detectores_activos) < 2:
            # Se requieren al menos 2 detectores confirmando
            return []
        
        # Determinar dirección mayoritaria
        direcciones = {}
        for detector_nombre in detectores_activos:
            resultado = resultados[detector_nombre]
            señal_core = resultado["senal"]
            if hasattr(señal_core, 'direccion'):
                dir_val = señal_core.direccion
                direcciones[dir_val] = direcciones.get(dir_val, 0) + 1
        
        if not direcciones:
            return []
        
        direccion = max(direcciones, key=direcciones.get)
        
        # Calcular confianza usando Wilson Score (Fase 7.2)
        from estrategias.pivot.scoring import scorer_global
        
        confianza, explicacion_scoring = scorer_global.obtener_confianza(
            detectores_activos=detectores_activos,
            direccion=direccion,
        )
        
        # Ajustar por tendencia D1
        if self.config.usar_trend_d1 and ctx.trend_d1 != "NEUTRO":
            if (direccion == 1 and ctx.trend_d1 == "ALCISTA") or \
               (direccion == -1 and ctx.trend_d1 == "BAJISTA"):
                confianza += 10
            else:
                confianza -= 15
        
        # Ajustar por kill zone
        if self.config.usar_kill_zones and ctx.kill_zone != "NONE":
            confianza += 5
        elif self.config.usar_kill_zones and ctx.session == "OUT":
            confianza -= 20
        
        # Verificar confianza mínima
        if confianza < self.config.confianza_minima:
            return []
        
        # Calcular niveles de entrada, SL y TP
        precio_actual = ctx.precio
        atr14 = ctx.g_atr14_buffer[0] if ctx.g_atr14_buffer else 0.0
        
        if atr14 <= 0:
            return []
        
        # Definir SL y TP basados en ATR
        if direccion == 1:  # LONG
            stop_loss = precio_actual - (atr14 * 1.5)
            take_profit = precio_actual + (atr14 * self.config.reward_ratio_min * 1.5)
        else:  # SHORT
            stop_loss = precio_actual + (atr14 * 1.5)
            take_profit = precio_actual - (atr14 * self.config.reward_ratio_min * 1.5)
        
        # Crear narrativa
        detectores_str = ", ".join(detectores_activos)
        narrativa = (f"Setup PIVOT {('LONG' if direccion == 1 else 'SHORT')} | "
                    f"Detectores: {detectores_str} | "
                    f"Estructura: {'válida' if estructura.valida else 'inválida'} | "
                    f"Confianza: {confianza:.0f}%")
        
        # Crear overlays para visualización
        overlays = [
            Overlay(
                tipo="marker",
                position="belowBar" if direccion == 1 else "aboveBar",
                shape="arrowUp" if direccion == 1 else "arrowDown",
                color="#00ff00" if direccion == 1 else "#ff0000",
                text="PIVOT",
                price=precio_actual,
                time=ctx.tiempo
            )
        ]
        
        # Añadir marcador de SL y TP
        if stop_loss:
            overlays.append(Overlay(
                tipo="line",
                color="#ff0000",
                price=stop_loss,
                extend="right"
            ))
        if take_profit:
            overlays.append(Overlay(
                tipo="line",
                color="#00ff00",
                price=take_profit,
                extend="right"
            ))
        
        # Crear señal
        señal = Señal(
            estrategia=self.nombre,
            simbolo=ctx.activo.simbolo if ctx.activo else "UNKNOWN",
            direccion=direccion,
            precio=precio_actual,
            tiempo=ctx.tiempo,
            etiqueta=f"PIVOT_{'.'.join(detectores_activos)}",
            stop_loss=stop_loss,
            take_profit=take_profit,
            expiracion_velas=self.config.expiracion_velas,
            confianza=(confianza, min(100, confianza + 10)),
            score=confianza / 100.0,
            narrativa=narrativa,
            contexto={
                "estructura": {
                    "swing_high": estructura.swing_high if estructura else 0,
                    "swing_low": estructura.swing_low if estructura else 0,
                    "zona": estructura.zona if estructura else "",
                },
                "detectores": detectores_activos,
                "trend_d1": ctx.trend_d1,
                "session": ctx.session,
                "kill_zone": ctx.kill_zone,
            },
            overlays=overlays,
            activa=True
        )
        
        return [señal]
    
    def on_backtest_tick(self, ctx: Contexto, operacion_abierta: bool) -> List[Señal]:
        """Hook especial para backtesting (opcional)."""
        return self.detectar(ctx)
