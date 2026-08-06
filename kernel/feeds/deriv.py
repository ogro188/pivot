"""
Feed en tiempo real desde Deriv API (WebSocket)
Soporta múltiples timeframes y reconexión automática
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Callable, Dict, Any, List
import websockets

logger = logging.getLogger(__name__)


class DerivConfig:
    """Configuración para conexión Deriv"""
    def __init__(
        self,
        app_id: int = 1089,
        symbol: str = "R_100",
        timeframes: List[str] = None
    ):
        self.app_id = app_id
        self.symbol = symbol
        self.timeframes = timeframes or ["M15", "H1"]


class DerivFeed:
    """
    Feed en tiempo real desde Deriv API
    
    Características:
    - Conexión WebSocket persistente
    - Reconexión automática con backoff exponencial
    - Soporte multi-timeframe
    - Callbacks asíncronos para nuevas velas
    - Buffer histórico opcional
    """
    
    WS_URL = "wss://ws.binaryws.com/websockets/v3"
    
    def __init__(self, config: DerivConfig):
        self.config = config
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.callbacks: Dict[str, List[Callable]] = {
            'candle': [],
            'tick': [],
            'error': [],
            'reconnect': []
        }
        self.buffers: Dict[str, List[Dict]] = {tf: [] for tf in config.timeframes}
        self.current_candles: Dict[str, Optional[Dict]] = {tf: None for tf in config.timeframes}
        self._task: Optional[asyncio.Task] = None
        self._reconnect_delay = 5
        self._max_reconnect_delay = 60
        
    def add_callback(self, event: str, callback: Callable):
        """Registrar callback para evento"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
        else:
            raise ValueError(f"Evento desconocido: {event}")
    
    def _trigger_callback(self, event: str, *args, **kwargs):
        """Ejecutar callbacks registrados"""
        for callback in self.callbacks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(*args, **kwargs))
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error en callback {event}: {e}")
    
    async def connect(self):
        """Establecer conexión WebSocket"""
        url = f"{self.WS_URL}?app_id={self.config.app_id}"
        try:
            self.ws = await websockets.connect(url, ping_interval=30, ping_timeout=10)
            logger.info(f"Conectado a Deriv API")
            
            # Suscribirse a ticks
            subscribe_msg = {
                "ticks": self.config.symbol,
                "subscribe": 1
            }
            await self.ws.send(json.dumps(subscribe_msg))
            logger.info(f"Suscrito a ticks de {self.config.symbol}")
            
            return True
        except Exception as e:
            logger.error(f"Error conectando a Deriv: {e}")
            return False
    
    async def _process_tick(self, tick_data: Dict[str, Any]):
        """Procesar tick recibido y actualizar velas"""
        quote = tick_data.get('quote')
        if not quote:
            return
            
        timestamp = datetime.fromtimestamp(tick_data.get('epoch', 0), tz=timezone.utc)
        price = float(quote)
        
        # Actualizar vela actual para cada timeframe
        for tf in self.config.timeframes:
            candle = self._update_candle(tf, timestamp, price)
            if candle:
                self._trigger_callback('candle', tf, candle)
    
    def _update_candle(self, tf: str, timestamp: datetime, price: float) -> Optional[Dict]:
        """Actualizar vela del timeframe especificado"""
        # Calcular inicio de vela
        tf_seconds = {
            'M1': 60, 'M5': 300, 'M15': 900, 'M30': 1800,
            'H1': 3600, 'H4': 14400, 'D1': 86400
        }.get(tf, 900)
        
        candle_start_ts = int(timestamp.timestamp()) // tf_seconds * tf_seconds
        candle_start = datetime.fromtimestamp(candle_start_ts, tz=timezone.utc)
        
        current = self.current_candles[tf]
        
        # Crear o actualizar vela actual
        if current is None or current['timestamp'] != candle_start:
            # Nueva vela - guardar la anterior si existe
            if current:
                pass  # Vela completada
            
            new_candle = {
                'timestamp': candle_start,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': 0
            }
            self.current_candles[tf] = new_candle
            self.buffers[tf].append(new_candle)
            
            # Mantener buffer limitado
            if len(self.buffers[tf]) > 500:
                self.buffers[tf] = self.buffers[tf][-500:]
            
            return new_candle
        else:
            # Actualizar vela existente
            current['high'] = max(current['high'], price)
            current['low'] = min(current['low'], price)
            current['close'] = price
            return current
    
    async def run(self):
        """Bucle principal de recepción de datos"""
        self.running = True
        
        while self.running:
            try:
                if not self.ws:
                    if not await self.connect():
                        await self._wait_reconnect()
                        continue
                
                message = await asyncio.wait_for(self.ws.recv(), timeout=30)
                data = json.loads(message)
                
                # Manejar diferentes tipos de mensajes
                if 'tick' in data:
                    await self._process_tick(data['tick'])
                elif 'error' in data:
                    logger.error(f"Error de Deriv: {data['error']}")
                    self._trigger_callback('error', data['error'])
                elif 'msg_type' in data and data['msg_type'] == 'subscription':
                    logger.info("Suscripción confirmada")
                    
            except asyncio.TimeoutError:
                try:
                    await self.ws.ping()
                except:
                    self.ws = None
            except websockets.ConnectionClosed:
                logger.warning("Conexión cerrada, reconectando...")
                self.ws = None
                self._trigger_callback('reconnect')
                await self._wait_reconnect()
            except Exception as e:
                logger.error(f"Error procesando mensaje: {e}")
                self.ws = None
                await self._wait_reconnect()
    
    async def _wait_reconnect(self):
        """Esperar antes de reconectar con backoff exponencial"""
        delay = min(self._reconnect_delay, self._max_reconnect_delay)
        logger.info(f"Reconectando en {delay}s...")
        await asyncio.sleep(delay)
        self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)
    
    def stop(self):
        """Detener feed"""
        self.running = False
        if self._task:
            self._task.cancel()
    
    def start(self):
        """Iniciar feed en background"""
        self._task = asyncio.create_task(self.run())
        return self._task
    
    def get_latest_candles(self, tf: str, count: int = 100) -> List[Dict]:
        """Obtener últimas N velas de un timeframe"""
        buffer = self.buffers.get(tf, [])
        return buffer[-count:]


class DerivHistoricalFeed:
    """
    Feed histórico desde Deriv API
    Obtiene velas históricas mediante API
    """
    
    def __init__(self, app_id: int = 1089):
        self.app_id = app_id
    
    async def fetch_history(
        self,
        symbol: str,
        granularity: int,
        count: int = 1000,
        end_time: Optional[int] = None
    ) -> List[Dict]:
        """
        Obtener historial de velas
        
        Args:
            symbol: Símbolo (ej. R_100, frxEURUSD)
            granularity: Granularidad en segundos
            count: Número de velas (máx 5000)
            end_time: Timestamp final
        
        Returns:
            Lista de velas como diccionarios
        """
        import aiohttp
        
        params = {
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": min(count, 5000),
            "end": end_time or int(datetime.now(timezone.utc).timestamp()),
            "granularity": granularity,
            "style": "candles",
            "app_id": self.app_id
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.deriv.com/websockets/v3",
                params=params
            ) as response:
                data = await response.json()
                
                if 'error' in data:
                    raise Exception(f"Error API Deriv: {data['error']}")
                
                candles_data = data.get('candles', [])
                candles = []
                
                for c in candles_data:
                    candle = {
                        'timestamp': datetime.fromtimestamp(c['epoch'], tz=timezone.utc),
                        'open': float(c['open']),
                        'high': float(c['high']),
                        'low': float(c['low']),
                        'close': float(c['close']),
                        'volume': int(c.get('volume', 0))
                    }
                    candles.append(candle)
                
                return candles
    
    def get_timeframe_granularity(self, tf: str) -> int:
        """Convertir timeframe a granularidad en segundos"""
        mapping = {
            'M1': 60, 'M5': 300, 'M15': 900, 'M30': 1800,
            'H1': 3600, 'H4': 14400, 'D1': 86400
        }
        return mapping.get(tf, 900)


def create_deriv_feed(
    symbol: str = "R_100",
    timeframes: List[str] = None,
    on_candle: Optional[Callable] = None
) -> DerivFeed:
    """Factory function para crear feed Deriv"""
    if timeframes is None:
        timeframes = ['M15', 'H1']
    
    config = DerivConfig(symbol=symbol, timeframes=timeframes)
    feed = DerivFeed(config)
    
    if on_candle:
        feed.add_callback('candle', on_candle)
    
    return feed
