"""Runtime: 1 hilo por activo. Cableado con Alertador y Consola."""
import queue
import threading
from datetime import datetime
import pandas as pd
from kernel.contrato import ActivoInfo, Estrategia, Contexto
from kernel.feeds.datafeed import DataFeed
from kernel.tiempo import ServicioTiempo
from kernel.señales import Latch, Medidor, _floor_to_timeframe
from kernel.storage import Storage
from kernel.alertas import Alertador
from kernel.consola import Consola


class ActivoRuntime(threading.Thread):
    def __init__(self, activo: ActivoInfo, fuente,
                 estrategias: list[Estrategia], storage: Storage,
                 ws_queue: queue.Queue, alertador: Alertador | None = None):
        super().__init__(daemon=True)
        self.activo = activo
        self.fuente = fuente
        self.estrategias = estrategias
        self.storage = storage
        self.ws_queue = ws_queue
        self.alertador = alertador
        self.feed = DataFeed(activo, fuente)
        self.tiempo = ServicioTiempo(activo.horario_broker_utc)
        self.latch = Latch()
        self.consola = Consola(activo.simbolo)
        self._running = False
        self._pending_signals: dict = {}
        self._signal_counter = 0

    def run(self) -> None:
        self._running = True
        self.feed.inicializar()
        self.fuente.conectar()
        self.consola.log("INFO", "MOTOR", f"Runtime iniciado para {self.activo.simbolo}")
        self.fuente.stream(
            on_tick=self._on_tick,
            on_candle=self._on_candle,
            on_error=self._on_error
        )

    def stop(self) -> None:
        self._running = False
        self.fuente.stop()
        self.consola.log("INFO", "MOTOR", f"Runtime detenido para {self.activo.simbolo}")

    def _on_tick(self, precio: float, tiempo: datetime) -> None:
        self.feed.on_tick(precio, tiempo)
        self._dispatch("tick", precio, tiempo)

    def _on_candle(self, tf: str, vela: pd.Series) -> None:
        self.feed.on_candle_close(tf, vela)
        self._dispatch("candle_close", float(vela["close"]), vela.name if hasattr(vela, 'name') and isinstance(vela.name, datetime) else datetime.utcnow())
        self._medir_pendientes(tf, vela)

    def _dispatch(self, evento: str, precio: float, tiempo: datetime) -> None:
        for estrategia in self.estrategias:
            if evento not in estrategia.eventos:
                continue
            ctx = Contexto(
                activo=self.activo,
                velas=self.feed.snapshot(),
                precio=precio,
                tiempo=tiempo,
                evento=evento,
                session=self.tiempo.get_session(tiempo),
                kill_zone=self.tiempo.get_kill_zone(tiempo)
            )
            ctx.indicador = self.feed.get_indicador
            try:
                senales = estrategia.detectar(ctx)
            except Exception as e:
                self._log_error(estrategia.nombre, e)
                continue
            for sig in senales:
                sig.simbolo = self.activo.simbolo
                sig.nivel_clave = estrategia.nivel_clave(sig)
                vela_ts = _floor_to_timeframe(tiempo, estrategia.timeframes[0])
                if not self.latch.check(sig.estrategia, sig.simbolo, sig.direccion,
                                        sig.nivel_clave, vela_ts, self.activo.point):
                    continue
                self._emitir_señal(sig)

    def _emitir_señal(self, sig) -> None:
        self._signal_counter += 1
        temp_id = self._signal_counter
        sig.id = temp_id
        self.storage.put_signal(sig)
        medidor = Medidor(sig, self.activo.point)
        self._pending_signals[temp_id] = medidor
        d = self._signal_to_dict(sig)
        self.ws_queue.put({"asset": self.activo.simbolo, "type": "signal", "data": d})
        self.consola.log("INFO", "SEÑAL", f"{sig.estrategia} {sig.etiqueta} @ {sig.precio}", sig.estrategia)
        if self.alertador:
            self.alertador.emitir(sig, self.activo)

    def _medir_pendientes(self, tf: str, vela: pd.Series) -> None:
        if tf != self.activo.timeframes[0]:
            return
        for sig_id, medidor in list(self._pending_signals.items()):
            medidor.on_candle(vela)
            if len(medidor.mediciones) >= medidor.signal.expiracion_velas:
                win, retorno = medidor.resultado()
                self.storage.put_result(sig_id, win, retorno)
                del self._pending_signals[sig_id]
                self.consola.log("INFO", "SEÑAL", f"Resultado #{sig_id}: {'WIN' if win else 'LOSS'} {retorno:.1f}p", medidor.signal.estrategia)

    def _log_error(self, estrategia: str, e: Exception) -> None:
        msg = str(e)
        self.storage.put_log(
            int(datetime.utcnow().timestamp() * 1000),
            "ERROR", self.activo.simbolo, estrategia,
            "ESTRATEGIA", msg, None
        )
        self.consola.log("ERROR", "ESTRATEGIA", msg, estrategia)

    def _signal_to_dict(self, sig):
        return {
            "id": sig.id, "ts": int(sig.tiempo.timestamp() * 1000),
            "asset": sig.simbolo, "estrategia": sig.estrategia,
            "etiqueta": sig.etiqueta, "direccion": sig.direccion,
            "precio": sig.precio, "expiracion_velas": sig.expiracion_velas,
            "confianza": sig.confianza, "objetivo": sig.objetivo,
            "invalidacion": sig.invalidacion, "narrativa": sig.narrativa,
            "estado": sig.estado
        }

    def get_history(self, tf: str, count: int = 200):
        """Devuelve velas del feed en memoria para el endpoint /history."""
        snap = self.feed.snapshot()
        df = snap.get(tf)
        if df is None or len(df) == 0:
            return []
        df = df.tail(count)
        records = []
        for ts, row in df.iterrows():
            records.append({
                "time": int(pd.Timestamp(ts).timestamp() * 1000) if not isinstance(ts, datetime) else int(ts.timestamp() * 1000),
                "open": float(row["open"]), "high": float(row["high"]),
                "low": float(row["low"]), "close": float(row["close"]),
                "volume": float(row.get("volume", 0))
            })
        return records


class MultiActivo:
    def __init__(self):
        self.runtimes: dict[str, ActivoRuntime] = {}

    def add(self, rt: ActivoRuntime) -> None:
        self.runtimes[rt.activo.simbolo] = rt
        rt.start()

    def stop(self, simbolo: str) -> None:
        if simbolo in self.runtimes:
            self.runtimes[simbolo].stop()
            del self.runtimes[simbolo]

    def stop_all(self) -> None:
        for rt in list(self.runtimes.values()):
            rt.stop()
        self.runtimes.clear()
