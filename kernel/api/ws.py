"""WebSocket endpoint único /ws con bridge thread-safe."""
import asyncio
import queue
import threading
from fastapi import APIRouter, WebSocket

router = APIRouter()
ws_queue: queue.Queue = queue.Queue()
_clients: list[WebSocket] = []
_lock = threading.Lock()


async def _broadcast(msg: dict):
    dead = []
    for client in _clients:
        try:
            await client.send_json(msg)
        except Exception:
            dead.append(client)
    for d in dead:
        try:
            _clients.remove(d)
        except ValueError:
            pass


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    with _lock:
        _clients.append(ws)
    try:
        while True:
            try:
                msg = ws_queue.get_nowait()
                await _broadcast(msg)
            except queue.Empty:
                await asyncio.sleep(0.05)
    except Exception:
        pass
    finally:
        with _lock:
            if ws in _clients:
                _clients.remove(ws)
