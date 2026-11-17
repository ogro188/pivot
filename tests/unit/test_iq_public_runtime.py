# -*- coding: utf-8 -*-
"""Tests del runtime OTC: SQLite del collector -> motor, sin red ni motor real.

Cubren:
- lectura read-only y filtro de velas cerradas;
- precarga silenciada (las señales del histórico no se persisten);
- emisión de señales nuevas con ``fuente='iqoption_public'``;
- OTC oculto: no difunde por WebSocket; al marcar ``visible`` sí difunde;
- arranque en frío cuando la DB aparece después del runtime.
"""
import asyncio
import importlib.util
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "iq_public_collector.py"
spec = importlib.util.spec_from_file_location("iq_public_collector_runtime_test", SCRIPT)
collector = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = collector
spec.loader.exec_module(collector)

from kernel import iq_public_runtime as runtime_module  # noqa: E402
from kernel.iq_public_runtime import (  # noqa: E402
    AssetIQPublicStream,
    IQPublicRuntime,
    IQPublicStore,
)

TF = 900
PROVIDER = "EURUSD-OTC"
SIMBOLO = "EURUSD-OTC"


class FakeAlertas:
    def __init__(self):
        self.ntfy_topic = "radar_test"
        self.g_alert_queue = []

    def build_alert_text(self, sig):
        return f"{sig.symbol} {sig.direction} {sig.tipo}"


class FakeEngine:
    """Genera una señal nueva en cada ``on_data`` (id incremental)."""

    def __init__(self, simbolo=SIMBOLO):
        self.symbol = simbolo
        self.alertas = FakeAlertas()
        self.g_pending_signals = []
        self.calls = []
        self.topicos_vistos = []
        self._next = 0

    def on_data(self, *dfs):
        self.calls.append(tuple(len(df) for df in dfs))
        self.topicos_vistos.append(self.alertas.ntfy_topic)
        self._next += 1
        self.g_pending_signals.append(SimpleNamespace(
            id=f"sig-{self._next}",
            entry_time=datetime.now(timezone.utc),
            entry_price=1.12345,
            hipotesis_objetivo=1.12400,
            invalidez_estructural=1.12200,
            symbol=self.symbol,
            tipo="PIVOT_TEST",
            detector="D2",
            direction=1,
            hipotesis_expiry_velas=8,
            hipotesis_prob_min=60,
            hipotesis_prob_max=70,
        ))


class FakeDB:
    def __init__(self):
        self.senales = []

    async def guardar_senal_core(self, **kwargs):
        self.senales.append(kwargs)


def _crear_db(path: Path) -> None:
    conn = collector.connect_db(path)
    try:
        collector.ensure_schema(conn)
    finally:
        conn.close()


def _insertar_velas(path: Path, fin_open: int, n: int, *, active_id: int = 76) -> None:
    """Inserta n velas M15 consecutivas que terminan en ``fin_open``."""
    conn = sqlite3.connect(path)
    try:
        for i in range(n):
            t = fin_open - (n - 1 - i) * TF
            base = 1.10000 + i * 0.00010
            conn.execute(
                """
                INSERT OR REPLACE INTO bars (
                    active_id, provider_name, timeframe, open_time, open, high,
                    low, close, bid_open, bid_close, ask_open, ask_close, ticks,
                    first_tick_ts, last_tick_ts
                ) VALUES (?, ?, 'M15', ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?, ?)
                """,
                (active_id, PROVIDER, t, base, base + 0.00020, base - 0.00020,
                 base + 0.00010, 50, t + 1, t + TF - 1),
            )
        conn.commit()
    finally:
        conn.close()


def _ultima_vela_cerrada() -> int:
    """Open time con margen de 3 buckets para poder insertar 2 velas cerradas."""
    ahora = int(time.time())
    return (ahora // TF - 3) * TF


def _insertar_charts(
    path: Path,
    desde: int,
    hasta: int,
    *,
    active_id: int = 76,
    provider_name: str = PROVIDER,
    precio: float = 1.10,
) -> None:
    """Inserta puntos chart_quotes por cada bucket M15 en [desde, hasta)."""
    conn = sqlite3.connect(path)
    try:
        filas = []
        t = desde
        while t < hasta:
            filas.append(
                (active_id, provider_name, "d1", t + 1, precio, time.time())
            )
            precio += 0.00001
            t += TF
        conn.executemany(
            """
            INSERT OR REPLACE INTO chart_quotes (
                active_id, provider_name, period, ts, price, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            filas,
        )
        conn.commit()
    finally:
        conn.close()


def _config(visible: bool = False):
    return {
        SIMBOLO: {
            "provider_name": PROVIDER,
            "active_id": 76,
            "visible": visible,
            "punto": 1e-05,
        }
    }


def _runtime(
    path: Path,
    db: FakeDB,
    visible: bool = False,
    broadcast=None,
    backfill: bool = True,
):
    return IQPublicRuntime(
        activos=_config(visible),
        db=db,
        store=IQPublicStore(str(path)),
        engine_factory=lambda simbolo, cfg: FakeEngine(simbolo),
        broadcast=broadcast,
        autopoll=False,
        backfill=backfill,
    )


def test_store_lee_solo_velas_cerradas(tmp_path):
    path = tmp_path / "iq.db"
    _crear_db(path)
    fin = _ultima_vela_cerrada()
    _insertar_velas(path, fin, 10)
    # Vela en curso (bucket actual): no debe considerarse cerrada.
    actual = int(time.time()) // TF * TF
    _insertar_velas(path, actual, 1)

    store = IQPublicStore(str(path))
    cerradas = store.bars(PROVIDER, "M15", closed_only=True)
    assert len(cerradas) == 10
    assert cerradas[-1]["time"] == fin

    todas = store.bars(PROVIDER, "M15")
    assert len(todas) == 11
    assert todas[-1]["time"] == actual


def test_precarga_silenciada_y_senal_nueva_persistida(tmp_path):
    path = tmp_path / "iq.db"
    _crear_db(path)
    fin = _ultima_vela_cerrada()
    _insertar_velas(path, fin, 60)

    db = FakeDB()
    runtime = _runtime(path, db)

    async def escenario():
        await runtime.start()
        stream = runtime.streams[SIMBOLO]

        # La precarga alimentó el motor y silenció su señal histórica.
        assert len(stream.buffer) == 60
        assert len(stream.engine.calls) == 1
        assert stream.engine.alertas.ntfy_topic == "radar_test"
        assert db.senales == []

        # Nueva vela cerrada -> señal persistida con la fuente OTC.
        _insertar_velas(path, fin + TF, 1)
        await stream.poll()
        assert len(stream.engine.calls) == 2
        assert len(db.senales) == 1
        assert db.senales[0]["fuente"] == "iqoption_public"
        assert db.senales[0]["symbol"] == SIMBOLO
        await runtime.stop()

    asyncio.run(escenario())


def test_oculto_no_difunde_y_visible_si(tmp_path):
    path = tmp_path / "iq.db"
    _crear_db(path)
    fin = _ultima_vela_cerrada()
    _insertar_velas(path, fin, 60)

    db = FakeDB()
    eventos = []

    async def broadcast(msg):
        eventos.append(msg)

    runtime = _runtime(path, db, visible=False, broadcast=broadcast)

    async def escenario():
        await runtime.start()
        stream = runtime.streams[SIMBOLO]

        _insertar_velas(path, fin + TF, 1)
        await stream.poll()
        assert len(db.senales) == 1
        assert eventos == [], "OTC oculto no debe difundir señales"

        stream.visible = True
        _insertar_velas(path, fin + 2 * TF, 1)
        await stream.poll()
        assert len(db.senales) == 2
        assert len(eventos) == 1
        assert eventos[0]["type"] == "signal"
        assert eventos[0]["data"]["asset"] == SIMBOLO
        assert eventos[0]["data"]["fuente"] == "iqoption_public"
        await runtime.stop()

    asyncio.run(escenario())


def test_history_incluye_vela_en_curso_y_resamplea(tmp_path):
    path = tmp_path / "iq.db"
    _crear_db(path)
    fin = _ultima_vela_cerrada()
    _insertar_velas(path, fin, 60)

    actual = int(time.time()) // TF * TF
    _insertar_velas(path, actual, 1)

    db = FakeDB()
    runtime = _runtime(path, db)

    async def escenario():
        await runtime.start()
        stream = runtime.streams[SIMBOLO]

        m15 = stream.history("M15", 200)
        assert len(m15) == 61
        assert m15[-1]["time"] == actual
        assert all(v["high"] >= v["open"] for v in m15)

        h1 = stream.history("H1", 200)
        assert 1 <= len(h1) <= 17
        assert h1[-1]["close"] == m15[-1]["close"]
        await runtime.stop()

    asyncio.run(escenario())


def test_arranque_en_frio_cuando_la_db_aparece_despues(tmp_path):
    path = tmp_path / "iq.db"
    db = FakeDB()
    runtime = _runtime(path, db)

    async def escenario():
        await runtime.start()
        stream = runtime.streams[SIMBOLO]
        assert runtime.status()["db_exists"] is False
        assert stream.connected is False
        assert len(stream.buffer) == 0

        # El collector recién crea la DB con histórico.
        _crear_db(path)
        fin = _ultima_vela_cerrada()
        _insertar_velas(path, fin, 60)

        await stream.poll()
        assert stream.connected is True
        assert len(stream.buffer) == 60
        # Es histórico: debe precargarse sin persistir señales.
        assert len(stream.engine.calls) == 1
        assert db.senales == []
        await runtime.stop()

    asyncio.run(escenario())


def test_vela_atrasada_no_emite_senal(tmp_path):
    """Una vela cerrada hace > 30 min se usa para indicadores, no para señales."""
    path = tmp_path / "iq.db"
    _crear_db(path)
    fin = _ultima_vela_cerrada() - 4 * TF
    _insertar_velas(path, fin, 60)

    db = FakeDB()
    runtime = _runtime(path, db)

    async def escenario():
        await runtime.start()
        stream = runtime.streams[SIMBOLO]

        # Hueco: el collector estuvo caído y aparecen varias velas viejas.
        _insertar_velas(path, fin + 2 * TF, 2)
        await stream.poll()
        assert len(stream.engine.calls) == 3  # precarga + 2 velas de catch-up
        assert db.senales == []
        await runtime.stop()

    asyncio.run(escenario())


def test_hueco_reconstruye_motor_fuera_del_event_loop(tmp_path):
    """El motor se reconstruye en un hilo, no dentro del loop de la API.

    ``PivotRadarEngine`` crea su propio event loop al cargar la cola pendiente.
    Si se construye dentro del loop de FastAPI falla con "Cannot run the event
    loop while another loop is running" y el stream queda mudo.
    """
    path = tmp_path / "iq.db"
    _crear_db(path)
    fin = _ultima_vela_cerrada() - 6 * TF
    _insertar_velas(path, fin, 60)

    llamadas = {"dentro_loop": 0}

    def factory(simbolo, cfg):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            llamadas["dentro_loop"] += 1
        return FakeEngine(simbolo)

    db = FakeDB()
    runtime = IQPublicRuntime(
        activos=_config(),
        db=db,
        store=IQPublicStore(str(path)),
        engine_factory=factory,
        autopoll=False,
    )

    async def escenario():
        await runtime.start()
        stream = runtime.streams[SIMBOLO]
        assert stream.engine is not None

        # Hueco de 1 h: se descarta el tramo anterior y se reconstruye el motor.
        _insertar_velas(path, fin + 4 * TF, 1)
        await stream.poll()

        assert stream.engine is not None
        assert llamadas["dentro_loop"] == 0
        assert len(stream.buffer) == 1
        assert stream.buffer[0]["time"] == fin + 4 * TF
        await runtime.stop()

    asyncio.run(escenario())


def test_motor_fallido_se_reintenta_en_el_siguiente_poll(tmp_path):
    """Un fallo transitorio al construir el motor no deja el stream mudo."""
    path = tmp_path / "iq.db"
    _crear_db(path)
    fin = _ultima_vela_cerrada() - 6 * TF
    _insertar_velas(path, fin, 60)

    intentos = {"n": 0}

    def factory(simbolo, cfg):
        intentos["n"] += 1
        if intentos["n"] == 2:
            raise RuntimeError("fallo transitorio")
        return FakeEngine(simbolo)

    db = FakeDB()
    runtime = IQPublicRuntime(
        activos=_config(),
        db=db,
        store=IQPublicStore(str(path)),
        engine_factory=factory,
        autopoll=False,
    )

    async def escenario():
        await runtime.start()
        stream = runtime.streams[SIMBOLO]

        _insertar_velas(path, fin + 4 * TF, 1)
        await stream.poll()
        assert stream.engine is None
        assert stream.status()["engine_ready"] is False

        await stream.poll()
        assert stream.engine is not None
        assert stream.status()["engine_ready"] is False  # aún hay 1 vela
        await runtime.stop()

    asyncio.run(escenario())


def test_historico_descarta_el_tramo_anterior_a_un_hueco(tmp_path):
    """Con un corte de horas, el motor solo recibe la racha continua final."""
    path = tmp_path / "iq.db"
    _crear_db(path)
    fin = _ultima_vela_cerrada()
    # Tramo viejo (30 velas) + hueco de ~2h45 + tramo final (30 velas).
    _insertar_velas(path, fin - 40 * TF, 30)
    _insertar_velas(path, fin, 30)

    db = FakeDB()
    runtime = _runtime(path, db)

    async def escenario():
        await runtime.start()
        stream = runtime.streams[SIMBOLO]
        assert len(stream.buffer) == 30
        assert stream.buffer[0]["time"] == fin - 29 * TF
        assert stream.buffer[-1]["time"] == fin
        await runtime.stop()

    asyncio.run(escenario())


def test_config_ntfy_por_activo_llega_al_stream(tmp_path):
    """El topic y servidor ntfy del JSON se propagan al stream."""
    path = tmp_path / "iq.db"
    _crear_db(path)
    _insertar_velas(path, _ultima_vela_cerrada(), 60)
    db = FakeDB()
    runtime = IQPublicRuntime(
        activos={
            SIMBOLO: {
                "provider_name": PROVIDER,
                "active_id": 76,
                "visible": False,
                "punto": 1e-05,
                "ntfy_topic": "radar_OTC_EURUSD",
                "ntfy_server": "http://127.0.0.1:8081",
            }
        },
        db=db,
        store=IQPublicStore(str(path)),
        engine_factory=lambda simbolo, cfg: FakeEngine(simbolo),
        autopoll=False,
    )

    async def escenario():
        await runtime.start()
        stream = runtime.streams[SIMBOLO]
        assert stream.ntfy_topic == "radar_OTC_EURUSD"
        assert stream.ntfy_server == "http://127.0.0.1:8081"
        await runtime.stop()

    asyncio.run(escenario())


def test_poll_reinicia_buffer_tras_un_hueco(tmp_path):
    """Si el collector estuvo caído, no se encadenan velas no consecutivas."""
    path = tmp_path / "iq.db"
    _crear_db(path)
    fin = _ultima_vela_cerrada() - 10 * TF
    _insertar_velas(path, fin, 30)

    db = FakeDB()
    runtime = _runtime(path, db)

    async def escenario():
        await runtime.start()
        stream = runtime.streams[SIMBOLO]
        motor_anterior = stream.engine
        assert len(stream.buffer) == 30

        # Aparece una vela 2 h después: hueco > 30 min.
        _insertar_velas(path, fin + 8 * TF, 1)
        await stream.poll()
        assert len(stream.buffer) == 1
        assert stream.engine is not motor_anterior
        assert db.senales == []
        await runtime.stop()

    asyncio.run(escenario())


def test_backfill_completa_el_buffer_al_arrancar(tmp_path, monkeypatch):
    """Con 20 velas reales, charts.d1 completa el calentamiento a 96."""
    # El helper deja 3 buckets de margen; el collector real refresca charts
    # cada 10 min, así que relajamos la frescura solo en el test.
    monkeypatch.setattr(runtime_module, "CHART_MAX_AGE", 7200)
    path = tmp_path / "iq.db"
    _crear_db(path)
    fin = _ultima_vela_cerrada()
    _insertar_velas(path, fin, 20)
    _insertar_charts(path, fin - 95 * TF, fin + TF)

    db = FakeDB()
    runtime = _runtime(path, db)

    async def escenario():
        await runtime.start()
        stream = runtime.streams[SIMBOLO]

        assert len(stream.buffer) == 96
        assert stream.status()["velas_sinteticas"] == 76
        assert stream.status()["engine_ready"] is True
        assert stream.status()["backfill"]["usado"] is True
        assert stream.status()["emision_suprimida_velas"] == 4
        assert len(stream.engine.calls) == 1
        assert db.senales == []
        await runtime.stop()

    asyncio.run(escenario())


def test_backfill_no_se_usa_si_las_velas_reales_alcanzan(tmp_path):
    path = tmp_path / "iq.db"
    _crear_db(path)
    fin = _ultima_vela_cerrada()
    _insertar_velas(path, fin, 60)
    _insertar_charts(path, fin - 96 * TF, fin + TF)

    db = FakeDB()
    runtime = _runtime(path, db)

    async def escenario():
        await runtime.start()
        stream = runtime.streams[SIMBOLO]

        assert len(stream.buffer) == 60
        assert stream.status()["velas_sinteticas"] == 0
        assert stream.status()["backfill"]["usado"] is False
        assert stream.status()["emision_suprimida_velas"] == 0
        await runtime.stop()

    asyncio.run(escenario())


def test_backfill_descarta_charts_atrasados(tmp_path):
    path = tmp_path / "iq.db"
    _crear_db(path)
    fin = _ultima_vela_cerrada()
    _insertar_velas(path, fin, 20)
    viejo = int(time.time()) - 7200
    conn = sqlite3.connect(path)
    try:
        conn.executemany(
            """
            INSERT INTO chart_quotes (active_id, provider_name, period, ts, price, fetched_at)
            VALUES (76, ?, 'd1', ?, 1.10, ?)
            """,
            [
                (PROVIDER, viejo + i * TF + 1, time.time() - 7200)
                for i in range(3)
            ],
        )
        conn.commit()
    finally:
        conn.close()

    db = FakeDB()
    runtime = _runtime(path, db)

    async def escenario():
        await runtime.start()
        stream = runtime.streams[SIMBOLO]

        assert len(stream.buffer) == 20
        assert stream.status()["engine_ready"] is False
        assert stream.status()["backfill"]["usado"] is False
        assert "atrasados" in (stream.status()["backfill"]["error"] or "")
        await runtime.stop()

    asyncio.run(escenario())


def test_backfill_deshabilitado_no_toca_el_buffer(tmp_path):
    path = tmp_path / "iq.db"
    _crear_db(path)
    fin = _ultima_vela_cerrada()
    _insertar_velas(path, fin, 20)
    _insertar_charts(path, fin - 76 * TF, fin + TF)

    db = FakeDB()
    runtime = _runtime(path, db, backfill=False)

    async def escenario():
        await runtime.start()
        stream = runtime.streams[SIMBOLO]

        assert len(stream.buffer) == 20
        assert stream.status()["velas_sinteticas"] == 0
        assert stream.status()["backfill"]["usado"] is False
        await runtime.stop()

    asyncio.run(escenario())


def test_hueco_se_cubre_con_charts_y_silencia_la_emision(tmp_path, monkeypatch):
    """Un hueco de 1 h se puentea con 3 sintéticas y luego se silencia 4 velas."""
    monkeypatch.setattr(runtime_module, "CHART_MAX_AGE", 7200)
    path = tmp_path / "iq.db"
    _crear_db(path)
    # Dejar 5 buckets cerrados por delante para probar la supresión.
    ultima = _ultima_vela_cerrada() - 3 * TF
    fin = ultima - 4 * TF
    _insertar_velas(path, fin, 60)
    # Charts de los buckets del hueco y del último cerrado (real).
    _insertar_charts(path, fin + TF, ultima + TF)

    db = FakeDB()
    runtime = _runtime(path, db)

    async def escenario():
        await runtime.start()
        stream = runtime.streams[SIMBOLO]
        assert stream.status()["velas_sinteticas"] == 0

        # Aparece la vela de las 11:45 tras 1 h sin datos.
        _insertar_velas(path, ultima, 1)
        await stream.poll()

        assert stream.engine is not None
        assert len(stream.buffer) == 64  # 60 reales + 3 sintéticas + 1 real
        assert stream.status()["velas_sinteticas"] == 3
        assert stream.status()["emision_suprimida_velas"] == 4
        assert stream.status()["backfill"]["usado"] is True
        assert db.senales == []
        # El motor se reconstruye: recibe una sola precarga con las 64 velas.
        assert len(stream.engine.calls) == 1
        assert stream.engine.calls[0][0] == 64

        # Las primeras 4 velas reales actualizan el motor pero no emiten.
        for i in range(1, 5):
            _insertar_velas(path, ultima + i * TF, 1)
            await stream.poll()
            assert db.senales == []
            assert stream.status()["emision_suprimida_velas"] == 4 - i

        # La quinta ya puede emitir.
        _insertar_velas(path, ultima + 5 * TF, 1)
        await stream.poll()
        assert len(db.senales) == 1
        # La precarga y las 4 velas suprimidas corren sin topic ntfy; solo la
        # vela que emite ve el topic real. Evita alertas durante el catch-up.
        assert stream.engine.topicos_vistos == [
            "", "", "", "", "", "radar_test",
        ]
        await runtime.stop()

    asyncio.run(escenario())
