"""Servicio de tiempo: sesiones y kill zones."""
from datetime import datetime, time, timedelta


class ServicioTiempo:
    def __init__(self, broker_utc_offset: int):
        self.offset = broker_utc_offset

    def _broker_time(self, dt: datetime) -> time:
        bt = dt + timedelta(hours=self.offset)
        return bt.time()

    def get_session(self, dt: datetime) -> str:
        t = self._broker_time(dt)
        if time(0, 0) <= t < time(8, 0):
            return "ASIA"
        if time(8, 0) <= t < time(17, 0):
            return "LONDON"
        if time(17, 0) <= t < time(18, 0):
            return "LONDON_CLOSE"
        if time(13, 0) <= t < time(22, 0):
            return "NY"
        return "OUT"

    def get_kill_zone(self, dt: datetime) -> str:
        t = self._broker_time(dt)
        if time(8, 0) <= t < time(10, 0):
            return "LONDON_OPEN"
        if time(13, 0) <= t < time(15, 0):
            return "NY_OPEN"
        if time(13, 0) <= t < time(17, 0):
            return "LONDON_NY_OVERLAP"
        return "NONE"

    def countdown_cierre_vela(self, dt: datetime, tf: str) -> int:
        tf_map = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}
        minutes = tf_map.get(tf, 15)
        epoch = dt.timestamp()
        period_sec = minutes * 60
        next_close = ((epoch // period_sec) + 1) * period_sec
        return int(next_close - epoch)
