"""Alertador vía ntfy.sh."""
import queue
import threading
import time
import requests
from kernel.contrato import Señal, ActivoInfo
from kernel.señales import _signal_id


class Alertador:
    def __init__(self, topic: str, server: str = "https://ntfy.sh"):
        self.topic = topic
        self.server = server
        self._cola: queue.Queue = queue.Queue()
        self._enviados: set = set()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def emitir(self, sig: Señal, activo: ActivoInfo) -> None:
        sid = _signal_id(sig)
        if sid in self._enviados:
            return
        self._enviados.add(sid)
        direccion_str = "CALL" if sig.direccion == 1 else "PUT"
        lineas = [
            "━━━━━━━━━━━━━━━━━━━━",
            f"RADAR | {sig.estrategia.upper()} | {direccion_str}",
            "━━━━━━━━━━━━━━━━━━━━",
            f"Activo: {sig.simbolo}",
            f"Precio: {sig.precio:.{activo.decimales}f}",
        ]
        if sig.objetivo:
            lineas.append(f"Objetivo: {sig.objetivo:.{activo.decimales}f}")
        if sig.invalidacion:
            lineas.append(f"Invalidación: {sig.invalidacion:.{activo.decimales}f}")
        if sig.nivel_clave:
            lineas.append(f"Nivel clave: {sig.nivel_clave:.{activo.decimales}f}")
        if sig.narrativa:
            lineas.append(f"Razón: {sig.narrativa}")
        if sig.metricas:
            lineas.append("Métricas:")
            for m in sig.metricas:
                lineas.append(f"  {m.label}: {m.value}{m.unit}")
        mensaje = "
".join(lineas)
        self._cola.put(mensaje)

    def _worker(self) -> None:
        while True:
            mensaje = self._cola.get()
            if mensaje is None:
                break
            self._enviar(mensaje)

    def _enviar(self, mensaje: str, intento: int = 0) -> None:
        max_intentos = 3
        backoff = 5 * (2 ** intento)
        try:
            requests.post(
                f"{self.server}/{self.topic}",
                data=mensaje.encode("utf-8"),
                headers={"Content-Type": "text/plain; charset=utf-8"},
                timeout=10
            )
        except Exception:
            if intento < max_intentos:
                time.sleep(backoff)
                self._enviar(mensaje, intento + 1)
