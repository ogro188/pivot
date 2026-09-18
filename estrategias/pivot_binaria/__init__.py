# -*- coding: utf-8 -*-
"""
Estrategia PIVOT Binaria - Adaptación de PIVOT para opciones binarias.
Combina los detectores D0-D5 para generar señales CALL/PUT con expiración fija.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from kernel.contrato_binario import (
    EstrategiaBinaria, SeñalBinaria, ConfiguracionBinaria, TipoOpcion
)
from kernel.contrato import Contexto, ActivoInfo
from kernel.core_adapter import CoreAdapter, actualizar_contexto_con_indicadores

# Importar detectores del core
from core.d1_ruptura import DetectorD1
from core.d2_sweep import DetectorD2
from core.d2_anticipacion import DetectorD2Anticipacion
from core.d3_fvg import DetectorD3
from core.d4_orderblock import DetectorD4
from core.d5_mss_sweep import DetectorD5


@dataclass
class ConfiguracionPivotBinaria(ConfiguracionBinaria):
    """Configuración específica para PIVOT en modo binario."""
    # Hereda todo de ConfiguracionBinaria
    
    # Parámetros específicos de PIVOT
    pivot_depth: int = 2
    pivot_lookback: int = 24
    n_ruptura: int = 4
    d1_atr_threshold: float = 0.50
    confianza_minima: float = 65.0  # Ligeramente más alta para binarias
    usar_kill_zones: bool = True
    usar_trend_d1: bool = True
    
    # Tiempos de expiración por timeframe
    expiracion_m15: int = 15   # Patrones en M15 → 15 min
    expiracion_m30: int = 30   # Patrones en M30 → 30 min
    expiracion_h1: int = 30    # Patrones en H1 → 30 min
    expiracion_h4: int = 60    # Patrones en H4 → 60 min


class EstrategiaPivotBinaria(EstrategiaBinaria):
    """
    Estrategia PIVOT adaptada para opciones binarias.
    
    Diferencias vs PIVOT tradicional:
    - No calcula SL/TP, solo dirección
    - Determina expiración óptima basada en el timeframe del patrón
    - Enfocada en probabilidad direccional pura
    - Filtra más estrictamente para evitar rangos laterales
    """
    
    nombre = "PIVOT_BINARIA"
    version = "1.0.0"
    timeframes = ["M15", "H1", "H4", "D1"]
    eventos = ["candle_close"]
    
    parametros = {
        "pivot_depth": {"tipo": "int", "default": 2, "min": 1, "max": 5},
        "pivot_lookback": {"tipo": "int", "default": 24, "min": 10, "max": 50},
        "n_ruptura": {"tipo": "int", "default": 4, "min": 2, "max": 10},
        "d1_atr_threshold": {"tipo": "float", "default": 0.50, "min": 0.1, "max": 2.0},
        "confianza_minima": {"tipo": "float", "default": 65.0, "min": 50.0, "max": 90.0},
        "usar_kill_zones": {"tipo": "bool", "default": True},
        "usar_trend_d1": {"tipo": "bool", "default": True},
    }
    
    def __init__(self):
        self.config: Optional[ConfiguracionPivotBinaria] = None
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
        
        # Scorer para confianza dinámica (opcional)
        self.scorer = None
    
    def setup(self, params: Dict[str, Any], activo: ActivoInfo, config_binaria: ConfiguracionBinaria) -> None:
        """Inicializa la estrategia."""
        self.activo_info = activo
        
        # Crear configuración combinando parámetros y config binaria
        self.config = ConfiguracionPivotBinaria(
            # Parámetros de PIVOT
            pivot_depth=params.get("pivot_depth", 2),
            pivot_lookback=params.get("pivot_lookback", 24),
            n_ruptura=params.get("n_ruptura", 4),
            d1_atr_threshold=params.get("d1_atr_threshold", 0.50),
            confianza_minima=params.get("confianza_minima", 65.0),
            usar_kill_zones=params.get("usar_kill_zones", True),
            usar_trend_d1=params.get("usar_trend_d1", True),
            # Heredar de config_binaria
            porcentaje_riesgo=config_binaria.porcentaje_riesgo,
            payout_call=config_binaria.payout_call,
            payout_put=config_binaria.payout_put,
            usar_martingale=config_binaria.usar_martingale,
            volatilidad_minima=config_binaria.volatilidad_minima,
            volatilidad_maxima=config_binaria.volatilidad_maxima,
        )
        
        # Inicializar adaptador
        self.adapter = CoreAdapter()
        
        # Inicializar scorer si hay DB
        try:
            from estrategias.pivot.scoring import WilsonScorer
            self.scorer = WilsonScorer(z_score=1.96, min_muestras=30)
            self._cargar_historial_scoring()
        except Exception:
            pass
    
    def detectar(self, ctx: Contexto) -> List[SeñalBinaria]:
        """
        Evalúa el contexto y genera señales binarias CALL/PUT.
        
        Flujo:
        1. Actualizar indicadores
        2. Adaptar contexto al formato del core
        3. Ejecutar detectores D0-D5
        4. Determinar dirección mayoritaria
        5. Calcular confianza
        6. Determinar expiración óptima
        7. Generar señal binaria
        """
        if not self.config or not self.adapter:
            return []
        
        # Actualizar indicadores
        actualizar_contexto_con_indicadores(ctx, "M15")
        
        # Adaptar contexto
        try:
            core_ctx = self.adapter.adaptar_contexto(ctx)
        except Exception as e:
            print(f"[PIVOT_BIN] Error adaptando contexto: {e}")
            return []
        
        # Aplicar parámetros
        core_ctx.inp_pivot_depth = self.config.pivot_depth
        core_ctx.inp_pivot_lookback = self.config.pivot_lookback
        core_ctx.inp_n_ruptura = self.config.n_ruptura
        core_ctx.inp_d1_atr_threshold = self.config.d1_atr_threshold
        
        # Obtener estructura (D0)
        estructura = self.adapter.obtener_estructura()
        if not estructura or not estructura.valida:
            return []
        
        # Ejecutar detectores
        resultados = self.adapter.ejecutar_detectores(list(self.detectores.values()))
        
        # Filtrar detectores con señales válidas
        detectores_activos = [
            k for k, v in resultados.items() 
            if "senal" in v and v.get("clasificacion") in ["A", "B"]
        ]
        
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
        
        # Calcular confianza
        confianza = 50.0
        if self.scorer:
            confianza, _ = self.scorer.obtener_confianza(
                detectores_activos=detectores_activos,
                direccion=direccion,
            )
        else:
            # Confianza base por número de detectores
            confianza = 55.0 + (len(detectores_activos) * 8)
        
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
        
        # Determinar tipo de opción
        tipo_opcion = TipoOpcion.CALL if direccion == 1 else TipoOpcion.PUT
        
        # Determinar expiración óptima
        expiracion = self.obtener_expiracion_optima(ctx, detectores_activos)
        
        # Obtener precio actual
        precio_actual = ctx.precio
        
        # Obtener ATR para filtros de volatilidad
        atr14 = ctx.g_atr14_buffer[0] if ctx.g_atr14_buffer else 0.0
        if atr14 <= 0:
            return []
        
        # Crear narrativa
        detectores_str = ", ".join(detectores_activos)
        narrativa = (
            f"Setup PIVOT BINARIA {tipo_opcion.value} | "
            f"Detectores: {detectores_str} | "
            f"Confianza: {confianza:.0f}% | "
            f"Expiración: {expiracion} min"
        )
        
        # Crear señal binaria
        señal = SeñalBinaria(
            estrategia=self.nombre,
            simbolo=ctx.activo.simbolo if ctx.activo else "UNKNOWN",
            tipo_opcion=tipo_opcion,
            precio_entrada=precio_actual,
            tiempo_entrada=ctx.tiempo,
            expiracion_minutos=expiracion,
            confianza=confianza,
            score=confianza / 100.0,
            detectores_activos=detectores_activos,
            narrativa=narrativa,
            contexto={
                "estructura": {
                    "swing_high": estructura.swing_high if estructura else 0,
                    "swing_low": estructura.swing_low if estructura else 0,
                },
                "trend_d1": ctx.trend_d1,
                "session": ctx.session,
                "kill_zone": ctx.kill_zone,
            },
            nivel_estructural=estructura.zona if estructura else 0,
            sweep_detectado="D2" in detectores_activos or "D5" in detectores_activos,
            fvg_presente="D3" in detectores_activos,
            orderblock_presente="D4" in detectores_activos,
            atr14=atr14,
            session=ctx.session or "UNKNOWN",
            kill_zone=ctx.kill_zone or "NONE",
            trend_d1=ctx.trend_d1,
            activa=True,
        )
        
        return [señal]
    
    def obtener_expiracion_optima(self, ctx: Contexto, detectores: List[str]) -> int:
        """
        Determina el tiempo de expiración óptimo basado en el contexto.
        
        Reglas:
        - Si hay MSS (D5) → Expiración más larga (necesita tiempo para desarrollarse)
        - Si es solo ruptura (D1) → Expiración media
        - Si hay sweep (D2) → Expiración corta (reacción rápida)
        """
        # Prioridad de detectores para determinar expiración
        if "D5" in detectores:  # MSS Sweep → más tiempo
            return self.config.expiracion_h4 if hasattr(ctx, 'df_h4') and ctx.df_h4 is not None else 30
        
        if "D4" in detectores:  # Order Block → tiempo medio
            return self.config.expiracion_h1
        
        if "D2" in detectores or "D2Ant" in detectores:  # Sweep → rápido
            return min(15, self.config.expiracion_m15)
        
        # Por defecto, basado en sesión
        if ctx.session == "LONDON":
            return 15  # Londres suele tener movimientos rápidos
        elif ctx.session == "NEWYORK":
            return 15  # NY también
        else:
            return 30  # Asia o fuera de sesión → más conservador
    
    def _cargar_historial_scoring(self):
        """Carga historial de señales previas desde la base de datos."""
        try:
            from kernel.storage import get_database
            db = get_database()
            with db._lock:
                cursor = db.conn.execute(
                    "SELECT detectores_activos, direccion, fue_ganadora FROM signals_ml_dataset WHERE fue_ganadora IS NOT NULL LIMIT 500"
                )
                filas = cursor.fetchall()
                for fila in filas:
                    detectores_str = fila[0] if fila[0] else ""
                    if detectores_str:
                        import json
                        try:
                            detectores = json.loads(detectores_str) if detectores_str.startswith('[') else detectores_str.split(',')
                        except Exception:
                            detectores = detectores_str.split(',')
                    else:
                        continue
                    direccion = fila[1]
                    resultado = fila[2] == 1
                    self.scorer.registrar_resultado(detectores, direccion, resultado)
        except Exception:
            pass
