"""Consola: buffer circular + archivo + WS."""
import json
from collections import deque
from datetime import datetime
from typing import TextIO


class Consola:
    def __init__(self, asset: str, max_buffer: int = 800):
        self.asset = asset
        self.buffer: deque = deque(maxlen=max_buffer)
        self._file: TextIO | None = None
        self._ws_callback = None

    def set_ws_callback(self, cb) -> None:
        self._ws_callback = cb

    def set_file(self, f: TextIO) -> None:
        self._file = f

    def log(self, level: str, categoria: str, mensaje: str,
            estrategia: str = "", contexto: dict | None = None,
            tiempo: datetime | None = None) -> dict:
        t = tiempo if tiempo is not None else datetime.utcnow()
        entry = {
            "ts": int(t.timestamp() * 1000),
            "t": t.strftime("%H:%M:%S"),
            "level": level,
            "cat": categoria,
            "msg": mensaje,
            "est": estrategia,
            "ctx": contexto
        }
        self.buffer.append(entry)
        if self._file:
            self._file.write(json.dumps(entry) + "
")
            self._file.flush()
        if self._ws_callback:
            self._ws_callback(self.asset, entry)
        return entry
