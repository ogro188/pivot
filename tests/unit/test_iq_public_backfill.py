# -*- coding: utf-8 -*-
"""Tests de las velas sintéticas de calentamiento desde ``charts``."""
from kernel.feeds.iq_public_backfill import fusionar_velas, quotes_to_m15

BASE = 1_700_000_000 // 900 * 900
TF = 900


def _real(t, close, *, open_=None):
    open_ = close if open_ is None else open_
    return {
        "time": t,
        "open": open_,
        "high": max(open_, close),
        "low": min(open_, close),
        "close": close,
        "volume": 10,
    }


def _synth(t, price):
    return {
        "time": t,
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": 0,
        "sintetica": True,
    }


def test_quotes_to_m15_agrupa_ohlc_y_descarta_la_vela_en_curso():
    quotes = [
        {"timestamp": BASE + 1, "price": 1.1000},
        {"timestamp": BASE + 400, "price": 1.1300},
        {"timestamp": BASE + 800, "price": 1.0500},
        {"timestamp": BASE + TF + 10, "price": 1.2000},  # en curso
        {"timestamp": BASE + TF + 20, "price": 1.2100},
    ]
    velas = quotes_to_m15(quotes, now=BASE + TF + 30)

    assert len(velas) == 1
    bar = velas[0]
    assert bar["time"] == BASE
    assert (bar["open"], bar["high"], bar["low"], bar["close"]) == (
        1.1000,
        1.1300,
        1.0500,
        1.0500,
    )
    assert bar["sintetica"] is True


def test_quotes_to_m15_deduplica_timestamps_y_ordena():
    quotes = [
        {"timestamp": BASE + TF + 1, "price": 1.30},
        {"timestamp": BASE + 1, "price": 1.10},
        {"timestamp": BASE + 1, "price": 1.15},
        {"timestamp": BASE, "price": 0},
    ]
    velas = quotes_to_m15(quotes, now=BASE + 2 * TF)

    assert [v["time"] for v in velas] == [BASE, BASE + TF]
    assert velas[0]["close"] == 1.15
    assert velas[1]["open"] == 1.30


def test_fusionar_prefiere_vela_real_y_rellena_el_hueco():
    reales = [_real(BASE + 4 * TF, 1.10)]
    sinteticas = [
        _synth(BASE + i * TF, 1.00 + i * 0.01) for i in range(4)
    ]

    velas, n_sinteticas = fusionar_velas(
        reales, sinteticas, now=BASE + 5 * TF
    )

    assert [v["time"] for v in velas] == [BASE + i * TF for i in range(5)]
    assert n_sinteticas == 4
    assert velas[-1]["sintetica"] is False
    assert velas[-1]["close"] == 1.10


def test_fusionar_desplaza_el_tramo_sintetico_entre_dos_reales():
    # Reales en 100 y 106; sintéticas crudas en 99 y 104.
    reales = [_real(BASE, 100.0), _real(BASE + 3 * TF, 106.0)]
    sinteticas = [_synth(BASE + TF, 99.0), _synth(BASE + 2 * TF, 104.0)]

    velas, n_sinteticas = fusionar_velas(
        reales, sinteticas, now=BASE + 4 * TF
    )

    assert n_sinteticas == 2
    assert [v["time"] for v in velas] == [BASE + i * TF for i in range(4)]
    # Bordes: la primera sintética cierra en 100 y la última abre/cierra en 106.
    assert velas[1]["close"] == 100.0
    assert velas[2]["close"] == 106.0
    assert velas[1]["sintetica"] is True


def test_fusionar_desplaza_prefijo_con_la_primera_vela_real():
    reales = [_real(BASE + 2 * TF, 100.0)]
    sinteticas = [_synth(BASE, 90.0), _synth(BASE + TF, 95.0)]

    velas, _ = fusionar_velas(reales, sinteticas, now=BASE + 3 * TF)

    # offset = 100 - 95 = 5
    assert velas[0]["close"] == 95.0
    assert velas[1]["close"] == 100.0
    assert velas[2]["close"] == 100.0


def test_fusionar_descarta_tramo_anterior_a_un_hueco_grande():
    reales = [_real(BASE + 6 * TF, 100.0)]
    sinteticas = [_synth(BASE, 90.0), _synth(BASE + TF, 91.0)]

    velas, n_sinteticas = fusionar_velas(
        reales, sinteticas, now=BASE + 7 * TF, max_gap=2 * TF
    )

    assert [v["time"] for v in velas] == [BASE + 6 * TF]
    assert n_sinteticas == 0


def test_fusionar_ignora_velas_en_curso():
    reales = [_real(BASE, 100.0), _real(BASE + TF, 101.0)]
    sinteticas = [_synth(BASE + 2 * TF, 102.0)]

    velas, _ = fusionar_velas(
        reales, sinteticas, now=BASE + 2 * TF + 1
    )

    assert [v["time"] for v in velas] == [BASE, BASE + TF]
