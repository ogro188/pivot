# -*- coding: utf-8 -*-
"""Tests unitarios de las utilidades del collector OTC (sin red)."""
import importlib.util
import sys
import time
from pathlib import Path

import pytest

from kernel.feeds.iqoption_public import Bar, IQChart, IQChartQuote

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "iq_public_collector.py"
spec = importlib.util.spec_from_file_location("iq_public_collector", SCRIPT)
collector = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = collector
spec.loader.exec_module(collector)


def test_parse_ids_deduplicates_and_rejects_invalid():
    assert collector.parse_ids("76, 1857 ,76") == [76, 1857]

    with pytest.raises(ValueError):
        collector.parse_ids("76,abc")
    with pytest.raises(ValueError):
        collector.parse_ids("0")
    with pytest.raises(ValueError):
        collector.parse_ids("")


def test_human_seconds_scales():
    assert collector.human_seconds(30) == "30s"
    assert collector.human_seconds(600) == "10.0m"
    assert collector.human_seconds(7200) == "2.0h"


def test_prune_ticks_keeps_bars_and_recent_ticks(tmp_path):
    db_path = tmp_path / "test.db"
    conn = collector.connect_db(db_path)
    collector.ensure_schema(conn)

    now = time.time()
    old_ts = now - 20 * 86400
    conn.executemany(
        """
        INSERT INTO ticks (active_id, provider_name, ts, price)
        VALUES (?, ?, ?, ?)
        """,
        [
            (76, "EURUSD-OTC", old_ts, 1.10),
            (76, "EURUSD-OTC", now, 1.11),
        ],
    )
    conn.execute(
        """
        INSERT INTO bars (
            active_id, provider_name, timeframe, open_time,
            open, high, low, close, ticks
        ) VALUES (76, 'EURUSD-OTC', 'M1', ?, 1.1, 1.1, 1.1, 1.1, 1)
        """,
        (int(old_ts),),
    )
    conn.commit()

    assert collector.prune_ticks(conn, 14) == 1
    remaining = conn.execute("SELECT COUNT(*) FROM ticks").fetchone()[0]
    bars = conn.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
    conn.close()

    assert remaining == 1
    assert bars == 1


def test_prune_ticks_zero_keeps_everything(tmp_path):
    db_path = tmp_path / "test.db"
    conn = collector.connect_db(db_path)
    collector.ensure_schema(conn)
    conn.execute(
        "INSERT INTO ticks (active_id, provider_name, ts, price) VALUES (76, 'EURUSD-OTC', 0, 1.0)"
    )
    conn.commit()

    assert collector.prune_ticks(conn, 0) == 0
    assert conn.execute("SELECT COUNT(*) FROM ticks").fetchone()[0] == 1
    conn.close()


def _bar(**overrides) -> Bar:
    values = dict(
        active_id=76,
        provider_name="EURUSD-OTC",
        timeframe="M15",
        open_time=900,
        open=1.1000,
        high=1.1200,
        low=1.0900,
        close=1.1100,
        bid_open=1.0999,
        bid_close=1.1099,
        ask_open=1.1001,
        ask_close=1.1101,
        ticks=10,
        first_tick_ts=901.0,
        last_tick_ts=950.0,
    )
    values.update(overrides)
    return Bar(**values)


def test_upsert_bars_merges_partials(tmp_path):
    db_path = tmp_path / "test.db"
    conn = collector.connect_db(db_path)
    collector.ensure_schema(conn)

    collector.upsert_bars(conn, [_bar()])
    collector.upsert_bars(
        conn,
        [
            _bar(
                open=1.1100,
                high=1.1300,
                low=1.0800,
                close=1.1150,
                ticks=20,
                first_tick_ts=960.0,
                last_tick_ts=1000.0,
            )
        ],
    )
    conn.commit()

    row = conn.execute("SELECT * FROM bars").fetchone()
    conn.close()

    assert row["open"] == 1.1000  # se conserva la primera apertura observada
    assert row["high"] == 1.1300
    assert row["low"] == 1.0800
    assert row["close"] == 1.1150
    assert row["ticks"] == 30
    assert row["first_tick_ts"] == 901.0
    assert row["last_tick_ts"] == 1000.0


def test_ntfy_notifier_envia_basic_auth(monkeypatch):
    capturado = {}

    class Respuesta:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=5):
        capturado["url"] = request.full_url
        capturado["auth"] = request.get_header("Authorization")
        return Respuesta()

    monkeypatch.setattr(collector.urllib.request, "urlopen", fake_urlopen)
    notifier = collector.NtfyNotifier(
        "http://127.0.0.1:8081",
        "radar_OTC_health",
        user="alertas",
        password="secreto",
    )

    assert notifier.send("hola") is True
    assert capturado["url"] == "http://127.0.0.1:8081/radar_OTC_health"
    assert capturado["auth"].startswith("Basic ")



def test_replace_chart_quotes_reemplaza_la_ventana(tmp_path):
    db_path = tmp_path / "test.db"
    conn = collector.connect_db(db_path)
    collector.ensure_schema(conn)

    chart = IQChart(
        active_id=76,
        provider_name="EURUSD-OTC",
        period="d1",
        quotes=(
            IQChartQuote(timestamp=900, price=1.10),
            IQChartQuote(timestamp=1800, price=1.11),
        ),
    )
    assert collector.replace_chart_quotes(conn, [chart]) == 2

    # La siguiente ventana móvil reemplaza la anterior, no acumula.
    chart2 = IQChart(
        active_id=76,
        provider_name="EURUSD-OTC",
        period="d1",
        quotes=(IQChartQuote(timestamp=1800, price=1.12),),
    )
    assert collector.replace_chart_quotes(conn, [chart2]) == 1

    rows = conn.execute(
        "SELECT ts, price FROM chart_quotes ORDER BY ts"
    ).fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0]["ts"] == 1800
    assert rows[0]["price"] == 1.12


def test_refresh_charts_tolera_fallos_de_red(tmp_path):
    db_path = tmp_path / "test.db"
    conn = collector.connect_db(db_path)
    collector.ensure_schema(conn)

    class ClienteRoto:
        def fetch_charts(self, ids, period="d1"):
            raise RuntimeError("sin red")

    assert collector.refresh_charts(conn, ClienteRoto(), [76]) == 0
    assert conn.execute("SELECT COUNT(*) FROM chart_quotes").fetchone()[0] == 0
    conn.close()
