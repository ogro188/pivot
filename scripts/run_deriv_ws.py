#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Punto de entrada para el servicio WebSocket de Deriv.
Se ejecuta como contenedor independiente (pivot-ws).
"""
import asyncio
import os
import signal
import sys
import logging
from typing import Optional

# Añadir el directorio raíz al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kernel.feeds.deriv import DerivFeed, DerivConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("deriv-ws")


async def run_deriv_feed():
    """Crea y ejecuta el feed Deriv hasta señal de parada."""
    app_id = int(os.getenv("DERIV_APP_ID", "1089"))
    symbol = os.getenv("DERIV_SYMBOL", "R_100")
    timeframes = os.getenv("DERIV_TIMEFRAMES", "M15,H1").split(",")
    ws_port = int(os.getenv("WS_PORT", "8765"))

    config = DerivConfig(app_id=app_id, symbol=symbol, timeframes=timeframes)
    feed = DerivFeed(config)

    # Callbacks básicos para logging
    def on_candle(tf: str, candle: dict):
        logger.debug(f"Candle {tf}: {candle}")

    def on_tick(tick: dict):
        logger.debug(f"Tick: {tick}")

    def on_error(error: Exception):
        logger.error(f"Error en DerivFeed: {error}")

    def on_reconnect(attempt: int, delay: float):
        logger.warning(f"Reconexión #{attempt} en {delay:.1f}s...")

    feed.add_callback("candle", on_candle)
    feed.add_callback("tick", on_tick)
    feed.add_callback("error", on_error)
    feed.add_callback("reconnect", on_reconnect)

    # Manejo de señales para shutdown limpio
    stop_event = asyncio.Event()

    def _signal_handler(signum, frame):
        logger.info(f"Señal {signum} recibida, cerrando...")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _signal_handler)
        except (OSError, ValueError):
            pass  # Windows o entorno sin señales

    logger.info(f"Iniciando DerivFeed: symbol={symbol}, timeframes={timeframes}")
    await feed.start()

    # Mantener vivo hasta stop
    await stop_event.wait()

    logger.info("Deteniendo DerivFeed...")
    await feed.stop()
    logger.info("DerivFeed detenido correctamente")


if __name__ == "__main__":
    try:
        asyncio.run(run_deriv_feed())
    except KeyboardInterrupt:
        logger.info("Interrumpido por usuario")
    except Exception as e:
        logger.exception(f"Error fatal: {e}")
        sys.exit(1)