"""
Sistema de almacenamiento SQLite para operaciones y métricas
"""
import asyncio, sqlite3, logging, json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from threading import Lock

logger = logging.getLogger(__name__)

class Database:
    """Gestor de base de datos SQLite thread-safe"""
    
    def __init__(self, db_path: str = "data/pivot.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._initialized = False
    
    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def initialize(self):
        if self._initialized:
            return
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS operaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estrategia TEXT, simbolo TEXT, timeframe TEXT,
            timestamp_abertura DATETIME, timestamp_cierre DATETIME,
            tipo TEXT, precio_entrada REAL, precio_salida REAL,
            stop_loss REAL, take_profit REAL, cantidad REAL,
            pnl REAL DEFAULT 0, estado TEXT DEFAULT 'ABIERTA',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS backtests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estrategia TEXT, simbolo TEXT, timeframe TEXT,
            fecha_inicio DATETIME, fecha_fin DATETIME,
            capital_inicial REAL, capital_final REAL,
            retorno_total REAL, win_rate REAL,
            total_operaciones INTEGER, profit_factor REAL,
            sharpe_ratio REAL, drawdown_max REAL,
            parametros JSON, metricas_json JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS activos_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            simbolo TEXT UNIQUE, nombre TEXT, tipo TEXT DEFAULT 'FOREX',
            precision INTEGER DEFAULT 5, pip_value REAL,
            spread_promedio REAL, timezone TEXT DEFAULT 'UTC',
            activo BOOLEAN DEFAULT 1
        )""")
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS strategy_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estrategia TEXT, simbolo TEXT, nivel TEXT,
            mensaje TEXT, contexto JSON,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        
        conn.commit()
        self._initialized = True
        logger.info(f"Base de datos inicializada: {self.db_path}")
    
    async def execute_async(self, query: str, params: tuple = ()):
        loop = asyncio.get_event_loop()
        def _execute():
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor
        return await loop.run_in_executor(None, _execute)
    
    async def fetchall_async(self, query: str, params: tuple = ()) -> List[Dict]:
        loop = asyncio.get_event_loop()
        def _fetch():
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        return await loop.run_in_executor(None, _fetch)
    
    async def fetchone_async(self, query: str, params: tuple = ()) -> Optional[Dict]:
        loop = asyncio.get_event_loop()
        def _fetch():
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(query, params)
                row = cursor.fetchone()
                return dict(row) if row else None
        return await loop.run_in_executor(None, _fetch)
    
    async def guardar_operacion(self, operacion, estrategia: str):
        self.initialize()
        query = """INSERT INTO operaciones (estrategia, simbolo, timeframe, timestamp_abertura, tipo, precio_entrada, cantidad, stop_loss, take_profit, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        params = (estrategia, operacion.simbolo, operacion.timeframe.name, operacion.timestamp_abertura, operacion.tipo.value if hasattr(operacion.tipo, 'value') else str(operacion.tipo), operacion.precio_entrada, operacion.cantidad, operacion.stop_loss, operacion.take_profit, operacion.estado)
        await self.execute_async(query, params)
    
    async def actualizar_operacion_cierre(self, operacion_id: int, operacion):
        self.initialize()
        query = """UPDATE operaciones SET timestamp_cierre=?, precio_salida=?, pnl=?, estado=? WHERE id=?"""
        params = (operacion.timestamp_cierre, operacion.precio_salida, operacion.pnl, operacion.estado, operacion_id)
        await self.execute_async(query, params)
    
    async def obtener_operaciones_abiertas(self, estrategia: str = None) -> List[Dict]:
        self.initialize()
        if estrategia:
            return await self.fetchall_async("SELECT * FROM operaciones WHERE estado='ABIERTA' AND estrategia=?", (estrategia,))
        return await self.fetchall_async("SELECT * FROM operaciones WHERE estado='ABIERTA'")
    
    async def obtener_historico_operaciones(self, estrategia: str = None, simbolo: str = None, limite: int = 1000) -> List[Dict]:
        self.initialize()
        conditions = []
        params = []
        if estrategia:
            conditions.append("estrategia=?")
            params.append(estrategia)
        if simbolo:
            conditions.append("simbolo=?")
            params.append(simbolo)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        return await self.fetchall_async(f"SELECT * FROM operaciones {where} ORDER BY timestamp_abertura DESC LIMIT ?", (*params, limite))
    
    async def guardar_backtest(self, resultado, parametros: Dict = None):
        self.initialize()
        metrics = resultado.to_dict() if hasattr(resultado, 'to_dict') else {}
        query = """INSERT INTO backtests (estrategia, simbolo, timeframe, fecha_inicio, fecha_fin, capital_inicial, capital_final, retorno_total, win_rate, total_operaciones, profit_factor, sharpe_ratio, drawdown_max, parametros, metricas_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        params = (resultado.estrategia, resultado.simbolo, resultado.timeframe.name if hasattr(resultado.timeframe, 'name') else str(resultado.timeframe), resultado.fecha_inicio, resultado.fecha_fin, resultado.capital_inicial, resultado.capital_final, resultado.retorno_total, resultado.win_rate, resultado.total_operaciones, metrics.get('profit_factor'), metrics.get('sharpe_ratio'), metrics.get('drawdown_max'), json.dumps(parametros or {}), json.dumps(metrics))
        await self.execute_async(query, params)
    
    async def obtener_backtests(self, estrategia: str = None, limite: int = 50) -> List[Dict]:
        self.initialize()
        if estrategia:
            return await self.fetchall_async("SELECT * FROM backtests WHERE estrategia=? ORDER BY created_at DESC LIMIT ?", (estrategia, limite))
        return await self.fetchall_async("SELECT * FROM backtests ORDER BY created_at DESC LIMIT ?", (limite,))
    
    async def guardar_activo_config(self, config: Dict[str, Any]):
        self.initialize()
        query = """INSERT OR REPLACE INTO activos_config (simbolo, nombre, tipo, precision, pip_value, spread_promedio, timezone, activo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
        params = (config.get('simbolo'), config.get('nombre'), config.get('tipo', 'FOREX'), config.get('precision', 5), config.get('pip_value'), config.get('spread_promedio'), config.get('timezone', 'UTC'), config.get('activo', 1))
        await self.execute_async(query, params)
    
    async def obtener_activos_config(self) -> List[Dict]:
        self.initialize()
        return await self.fetchall_async("SELECT * FROM activos_config WHERE activo=1")
    
    async def log_strategy(self, estrategia: str, nivel: str, mensaje: str, simbolo: str = None, contexto: Dict = None):
        self.initialize()
        query = """INSERT INTO strategy_logs (estrategia, simbolo, nivel, mensaje, contexto) VALUES (?, ?, ?, ?, ?)"""
        params = (estrategia, simbolo, nivel, mensaje, json.dumps(contexto or {}))
        await self.execute_async(query, params)
    
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

_db_instance: Optional[Database] = None

def get_database(db_path: str = "data/pivot.db") -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
    return _db_instance
