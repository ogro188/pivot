"""
Runtime multi-activo para ejecución en tiempo real
Gestión de hilos por activo, colas thread-safe, reconciliación
"""

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Type, Any, Union
from collections import deque
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import time

from .contrato import Estrategia, Contexto, Señal, ActivoInfo
from .backtest import BacktestEngine, Operacion
from .storage import Database, get_database
from .feeds.csv import CSVFeed
from .core_adapter import CoreAdapter

logger = logging.getLogger(__name__)


@dataclass
class RuntimeConfig:
    """Configuración del runtime"""
    simbolos: List[str]
    estrategia_cls: Type[Estrategia]
    timeframe_principal: str = "M15"
    timeframes_secundarios: List[str] = None
    capital_inicial: float = 10000.0
    riesgo_por_operacion: float = 1.0
    usar_backtest_data: bool = False
    ruta_datos: str = "data"
    db_path: str = "data/pivot.db"
    
    def __post_init__(self):
        if self.timeframes_secundarios is None:
            self.timeframes_secundarios = ["H1", "H4", "D1"]


class AssetRuntime:
    """
    Runtime individual para un activo
    Ejecuta en hilo dedicado con su propio contexto
    """
    
    def __init__(
        self,
        simbolo: str,
        estrategia_cls: Type[Estrategia],
        config: RuntimeConfig,
        db: Database
    ):
        self.simbolo = simbolo
        self.estrategia_cls = estrategia_cls
        self.config = config
        self.db = db
        
        self.estrategia: Optional[Estrategia] = None
        self.contexto: Optional[Contexto] = None
        self.adapter: Optional[CoreAdapter] = None
        
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._queue = deque(maxlen=1000)  # Cola de velas nuevas
        self._operaciones_abiertas: Dict[int, Operacion] = {}
        self._db_lock = threading.Lock()
        
        # Callbacks
        self.on_signal: Optional[Callable] = None
        self.on_operation: Optional[Callable] = None
    
    def initialize(self):
        """Inicializar estrategia y contexto"""
        logger.info(f"Inicializando runtime para {self.simbolo}")
        
        # Crear adaptador Core
        self.adapter = CoreAdapter()
        
        # Crear estrategia
        self.estrategia = self.estrategia_cls()
        
        # Crear contexto inicial vacío
        self.contexto = Contexto(
            activo=ActivoInfo(
                simbolo=self.simbolo,
                nombre=self.simbolo,
                tipo='FOREX',
                precision=5,
                pip_value=10.0,
                spread_promedio=0.0001
            ),
            timeframe=self.config.timeframe_principal,
            capital=self.config.capital_inicial
        )
        
        logger.info(f"✓ Runtime {self.simbolo} inicializado")
    
    def push_candle(self, candle: Dict[str, Any], timeframe: str):
        """Encolar nueva vela para procesamiento"""
        self._queue.append((candle, timeframe))
    
    def _process_queue(self):
        """Proprimir cola de velas pendientes"""
        while self._queue and self.running:
            try:
                candle, tf = self._queue.popleft()
                self._process_candle(candle, tf)
            except Exception as e:
                logger.error(f"Error procesando vela {self.simbolo}: {e}")
    
    def _process_candle(self, candle: Dict[str, Any], timeframe: str):
        """Procesar una vela individual"""
        if not self.contexto or not self.estrategia:
            return
        
        # Actualizar contexto con nueva vela
        self._update_contexto(candle, timeframe)
        
        # Verificar si hay señal
        try:
            señal = self.estrategia.generar_señal(self.contexto)
            
            if señal and señal.confianza >= self.estrategia.parametros.get('confianza_minima', 65):
                logger.info(
                    f"🎯 SEÑAL {self.simbolo} - {señal.tipo.name} "
                    f"(confianza: {señal.confianza:.1f}%)"
                )
                
                # Ejecutar operación
                self._ejecutar_operacion(señal)
                
                # Callback
                if self.on_signal:
                    self.on_signal(self.simbolo, señal)
            
            # Gestionar operaciones abiertas
            self._gestionar_operaciones(candle)
            
        except Exception as e:
            logger.error(f"Error generando señal {self.simbolo}: {e}")
    
    def _update_contexto(self, candle: Dict[str, Any], timeframe: str):
        """Actualizar contexto con nueva vela"""
        # Agregar vela al dataframe correspondiente
        tf_name = timeframe.name
        
        if tf_name not in self.contexto.df:
            self.contexto.df[tf_name] = []
        
        self.contexto.df[tf_name].append(candle)
        
        # Mantener histórico limitado
        max_bars = 500
        if len(self.contexto.df[tf_name]) > max_bars:
            self.contexto.df[tf_name] = self.contexto.df[tf_name][-max_bars:]
        
        # Actualizar última vela
        self.contexto.ultima_vela = candle
        self.contexto.timestamp_actual = candle.timestamp
    
    def _ejecutar_operacion(self, señal: Señal):
        """Ejecutar operación basada en señal"""
        if not self.contexto:
            return
        
        # Calcular tamaño de posición
        riesgo_usd = self.contexto.capital * (self.config.riesgo_por_operacion / 100)
        sl_distance = abs(señal.stop_loss - señal.precio_entrada)
        
        if sl_distance == 0:
            logger.warning("Stop Loss inválido, skipping operación")
            return
        
        # Tamaño en lotes (simplificado para Forex)
        lotes = riesgo_usd / (sl_distance * 100000)  # 1 lote = 100k unidades
        
        operacion = Operacion(
            simbolo=self.simbolo,
            timeframe=self.contexto.timeframe,
            tipo=señal.tipo,
            precio_entrada=señal.precio_entrada,
            stop_loss=señal.stop_loss,
            take_profit=señal.take_profit,
            cantidad=lotes,
            timestamp_abertura=self.contexto.timestamp_actual,
            razon_entrada=señal.narrativa or "Señal estrategia"
        )
        
        # Guardar en DB (síncrono, funciona desde cualquier hilo)
        try:
            with self._db_lock:
                conn = self.db._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO operaciones (estrategia, simbolo, timeframe, 
                    timestamp_abertura, tipo, precio_entrada, cantidad, 
                    stop_loss, take_profit, estado) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.estrategia.nombre,
                    operacion.simbolo,
                    operacion.timeframe.name if hasattr(operacion.timeframe, 'name') else str(operacion.timeframe),
                    operacion.timestamp_abertura,
                    operacion.tipo.value if hasattr(operacion.tipo, 'value') else str(operacion.tipo),
                    operacion.precio_entrada,
                    operacion.cantidad,
                    operacion.stop_loss,
                    operacion.take_profit,
                    operacion.estado
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error guardando operación: {e}")
        
        # Tracking local
        self._operaciones_abiertas[id(operacion)] = operacion
        
        logger.info(
            f"📊 OPERACIÓN {self.simbolo}: {señal.tipo.name} @ {señal.precio_entrada:.5f} | "
            f"SL: {señal.stop_loss:.5f} | TP: {señal.take_profit:.5f} | "
            f"Lotes: {lotes:.2f}"
        )
        
        if self.on_operation:
            self.on_operation(self.simbolo, operacion)
    
    def _gestionar_operaciones(self, candle: Dict[str, Any]):
        """Gestionar operaciones abiertas (TP/SL/expiración)"""
        cerrar = []
        
        for op_id, op in self._operaciones_abiertas.items():
            razon_cierre = None
            
            # Verificar TP
            if op.tipo.value == 'LONG' and candle.close >= op.take_profit:
                razon_cierre = "Take Profit"
            elif op.tipo.value == 'SHORT' and candle.close <= op.take_profit:
                razon_cierre = "Take Profit"
            
            # Verificar SL
            elif op.tipo.value == 'LONG' and candle.close <= op.stop_loss:
                razon_cierre = "Stop Loss"
            elif op.tipo.value == 'SHORT' and candle.close >= op.stop_loss:
                razon_cierre = "Stop Loss"
            
            # Cerrar si corresponde
            if razon_cierre:
                op.cerrar(
                    precio_salida=candle.close,
                    timestamp_cierre=candle.timestamp,
                    razon=razon_cierre
                )
                cerrar.append(op_id)
        
        # Remover operaciones cerradas
        for op_id in cerrar:
            op = self._operaciones_abiertas.pop(op_id)
            # Actualizar en DB (síncrono, funciona desde cualquier hilo)
            try:
                with self._db_lock:
                    conn = self.db._get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE operaciones 
                        SET precio_salida = ?, timestamp_cierre = ?, 
                            razon_cierre = ?, estado = ?,
                            pnl = ?, pnl_porcentaje = ?
                        WHERE id = ?
                    """, (
                        op.precio_salida,
                        op.timestamp_cierre,
                        op.razon_cierre,
                        op.estado,
                        op.pnl,
                        op.pnl_porcentaje,
                        id(op)
                    ))
                    conn.commit()
            except Exception as e:
                logger.error(f"Error actualizando operación: {e}")
    
    def _run_loop(self):
        """Bucle principal del hilo"""
        self.initialize()
        
        while self.running:
            try:
                self._process_queue()
                time.sleep(0.1)  # Evitar busy waiting
            except Exception as e:
                logger.error(f"Error en loop {self.simbolo}: {e}")
        
        logger.info(f"Runtime {self.simbolo} detenido")
    
    def start(self):
        """Iniciar hilo de ejecución"""
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"▶️  Runtime {self.simbolo} iniciado (hilo {self._thread.ident})")
    
    def stop(self):
        """Detener hilo de ejecución"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info(f"⏹️  Runtime {self.simbolo} detenido")


class MultiAssetRuntime:
    """
    Gestor de runtimes multi-activo
    Coordina múltiples AssetRuntime en paralelo
    """
    
    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.db = get_database(config.db_path)
        self.runtimes: Dict[str, AssetRuntime] = {}
        self.running = False
        
        # Feed de datos
        self.feed: Optional[CSVFeed] = None
        
        # Executor para tareas asíncronas
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    async def initialize(self):
        """Inicializar todos los componentes"""
        logger.info("Inicializando Multi-Asset Runtime...")
        
        # Inicializar DB
        self.db.initialize()
        
        # Crear runtimes por activo
        for simbolo in self.config.simbolos:
            runtime = AssetRuntime(
                simbolo=simbolo,
                estrategia_cls=self.config.estrategia_cls,
                config=self.config,
                db=self.db
            )
            self.runtimes[simbolo] = runtime
        
        logger.info(f"✓ {len(self.runtimes)} runtimes inicializados")
    
    async def start(self):
        """Iniciar todos los runtimes"""
        logger.info("🚀 Iniciando runtimes...")
        
        for simbolo, runtime in self.runtimes.items():
            runtime.start()
        
        self.running = True
        
        # Si usa datos históricos, iniciar feed
        if self.config.usar_backtest_data:
            await self._start_historical_feed()
    
    async def _start_historical_feed(self):
        """Iniciar feed desde archivos CSV"""
        logger.info("Cargando datos históricos...")
        
        for simbolo in self.config.simbolos:
            ruta_csv = f"{self.config.ruta_datos}/{simbolo.lower()}_m15.csv"
            
            try:
                feed = CSVFeed(ruta_csv, Timeframe.M15)
                velas = list(feed)
                
                logger.info(f"✓ {simbolo}: {len(velas)} velas cargadas")
                
                # Push al runtime
                for vela in velas:
                    self.runtimes[simbolo].push_candle(vela, self.config.timeframe_principal)
                    
            except FileNotFoundError:
                logger.warning(f"⚠️  No se encontró {ruta_csv}")
    
    async def stop(self):
        """Detener todos los runtimes"""
        logger.info("Deteniendo runtimes...")
        
        self.running = False
        
        for runtime in self.runtimes.values():
            runtime.stop()
        
        self.executor.shutdown(wait=True)
        self.db.close()
        
        logger.info("✓ Todos los runtimes detenidos")
    
    def get_status(self) -> Dict:
        """Obtener estado del sistema"""
        return {
            'running': self.running,
            'activos': list(self.runtimes.keys()),
            'operaciones_abiertas': sum(
                len(rt._operaciones_abiertas) for rt in self.runtimes.values()
            ),
            'db_path': str(self.db.db_path)
        }


async def create_runtime(
    simbolos: List[str],
    estrategia_cls: Type[Estrategia],
    **kwargs
) -> MultiAssetRuntime:
    """Factory function para crear runtime"""
    config = RuntimeConfig(simbolos=simbolos, estrategia_cls=estrategia_cls, **kwargs)
    runtime = MultiAssetRuntime(config)
    await runtime.initialize()
    return runtime
