"""Fuente de datos WebSocket para Deriv + API REST para histórico."""
import json
import threading
import time
from datetime import datetime, timezone
import pandas as pd
import requests
import websocket
from kernel.contrato import FuenteDatos


class DerivFeed(FuenteDatos):
    """Feed Deriv funcional: carga histórico vía REST, streaming vía WS."""

    GRANULARITY = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}

    def __init__(self, instrumento: str, app_id: int = 1089,
                 ws_url: str = "wss://ws.binaryws.com/websockets/v3"):
        self.instrumento = instrumento
        self.app_id = app_id
        self.ws_url = f"{ws_url}?app_id={app_id}"
        self.ws = None
        self._conectado = False
        self._stop = False
        self._thread: threading.Thread | None = None
        self._last_tick = 0.0
        self._history: dict[str, pd.DataFrame] = {}
        self._on_tick_cb = None
        self._on_candle_cb = None
        self._on_error_cb = None

    def conectar(self) -> None:
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        for _ in range(100):
            if self._conectado:
                break
            time.sleep(0.05)

    def _run(self) -> None:
        def on_open(ws):
            ws.send(json.dumps({"ticks": self.instrumento, "subscribe": 1}))

        def on_message(ws, msg):
            data = json.loads(msg)
            if "tick" in data:
                self._last_tick = float(data["tick"]["quote"])
                ts = datetime.fromtimestamp(data["tick"]["epoch"], tz=timezone.utc)
                if self._on_tick_cb:
                    self._on_tick_cb(self._last_tick, ts)
            if "error" in data:
                if self._on_error_cb:
                    self._on_error_cb(Exception(data["error"].get("message", "Deriv error")))
            self._conectado = True

        def on_close(ws, *args):
            self._conectado = False

        self.ws = websocket.WebSocketApp(
            self.ws_url, on_open=on_open, on_message=on_message, on_close=on_close,
            on_error=lambda ws, e: self._on_error_cb and self._on_error_cb(e)
        )
        self._conectado = True
        self.ws.run_forever()

    def get_candles(self, tf: str, count: int) -> pd.DataFrame:
        """Carga histórico vía API REST de Deriv."""
        gran = self.GRANULARITY.get(tf, 900)
        url = f"https://ticks.binary.com/api/ticks_history"
        payload = {
            "ticks_history": self.instrumento,
            "adjust_start_time": 1,
            "count": min(count, 5000),
            "end": "latest",
            "start": 1,
            "style": "candles",
            "granularity": gran
        }
        try:
            r = requests.post(url, json=payload, timeout=30)
            data = r.json()
            candles = data.get("candles", [])
            if not candles:
                return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
            rows = []
            for c in candles:
                rows.append({
                    "open": float(c["open"]),
                    "high": float(c["high"]),
                    "low": float(c["low"]),
                    "close": float(c["close"]),
                    "volume": float(c.get("volume", 0)),
                    "time": datetime.fromtimestamp(c["epoch"], tz=timezone.utc)
                })
            df = pd.DataFrame(rows)
            df.set_index("time", inplace=True)
            return df
        except Exception as e:
            if self._on_error_cb:
                self._on_error_cb(e)
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    def stream(self, on_tick, on_candle, on_error):
        self._on_tick_cb = on_tick
        self._on_candle_cb = on_candle
        self._on_error_cb = on_error
        while not self._stop:
            time.sleep(1)

    def stop(self) -> None:
        self._stop = True
        if self.ws:
            self.ws.close()

    @property
    def conectado(self) -> bool:
        return self._conectado
