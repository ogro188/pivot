# -*- coding: utf-8 -*-
"""Tests unitarios del cliente IQ público y del constructor de velas."""
import json

import pytest

from kernel.feeds.iqoption_public import (
    BarBuilder,
    IQActiveQuote,
    IQPublicClient,
    IQPublicError,
    bucket_start,
)

BASE = 1_699_999_200  # divisible por 900 y 60, alineado a UTC


def _quote(ts: float, price: float, active_id: int = 76, name: str = "EURUSD-OTC") -> IQActiveQuote:
    return IQActiveQuote(
        active_id=active_id,
        provider_name=name,
        ticker=name.replace("-OTC", ""),
        is_otc=True,
        price=price,
        bid=price - 0.00001,
        ask=price + 0.00001,
        payout_turbo_pct=85.0,
        payout_binary_pct=86.0,
        session_open=1.0,
        session_close=1.1,
        received_at=ts,
        latency_ms=100.0,
    )


class _FakeHttpResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, response: _FakeHttpResponse):
        self.response = response
        self.headers: dict = {}
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return self.response

    def close(self):
        pass


def test_bucket_start_aligns_utc():
    assert bucket_start(BASE + 0.1, "M15") == BASE
    assert bucket_start(BASE + 899.9, "M15") == BASE
    assert bucket_start(BASE + 900.0, "M15") == BASE + 900
    assert bucket_start(BASE + 60.0, "M1") == BASE + 60


def test_m15_ohlc_and_close():
    builder = BarBuilder(("M15",))
    assert builder.add(_quote(BASE + 1, 1.1000)) == []
    assert builder.add(_quote(BASE + 100, 1.1200)) == []
    assert builder.add(_quote(BASE + 200, 1.0500)) == []

    closed = builder.add(_quote(BASE + 901, 1.3000))
    assert len(closed) == 1
    bar = closed[0]
    assert bar.open_time == BASE
    assert (bar.open, bar.high, bar.low, bar.close) == (1.1000, 1.1200, 1.0500, 1.0500)
    assert bar.ticks == 3
    assert bar.first_tick_ts == BASE + 1
    assert bar.last_tick_ts == BASE + 200

    current = builder.current(76, "M15")
    assert current is not None
    assert current.open_time == BASE + 900
    assert current.open == 1.3000


def test_m1_and_m15_close_independently():
    builder = BarBuilder(("M1", "M15"))
    builder.add(_quote(BASE + 1, 1.10))
    builder.add(_quote(BASE + 59, 1.11))

    closed = builder.add(_quote(BASE + 61, 1.12))
    assert [bar.timeframe for bar in closed] == ["M1"]
    assert closed[0].open_time == BASE
    assert closed[0].close == 1.11

    closed = builder.add(_quote(BASE + 901, 1.20))
    assert {bar.timeframe for bar in closed} == {"M1", "M15"}
    m15 = next(bar for bar in closed if bar.timeframe == "M15")
    assert m15.open_time == BASE
    assert m15.close == 1.12


def test_gap_closes_previous_and_does_not_invent_bars():
    builder = BarBuilder(("M15",))
    builder.add(_quote(BASE + 1, 1.10))
    closed = builder.add(_quote(BASE + 1801, 1.20))

    assert len(closed) == 1
    assert closed[0].open_time == BASE
    current = builder.current(76, "M15")
    assert current is not None
    assert current.open_time == BASE + 1800
    assert current.open == 1.20


def test_late_tick_is_ignored():
    builder = BarBuilder(("M15",))
    builder.add(_quote(BASE + 1, 1.10))
    builder.add(_quote(BASE + 1801, 1.20))
    current_before = builder.current(76, "M15")
    assert current_before is not None
    close_before = current_before.close

    assert builder.add(_quote(BASE + 901, 1.99)) == []
    current_after = builder.current(76, "M15")
    assert current_after is not None
    assert current_after.open_time == BASE + 1800
    assert current_after.close == close_before


def test_quote_parses_provider_name_and_payouts():
    item = {
        "id": 76,
        "ticker": "EURUSD",
        "providerName": "EURUSD-OTC",
        "isOTC": True,
        "price": 1.12345,
        "quotation": {"bid": 1.12344, "ask": 1.12346},
        "payoutTurbo": 85,
        "payoutBinary": 86,
        "sessionStat": {"open": 1.10, "close": 1.13},
    }
    quote = IQActiveQuote.from_graphql(item, received_at=123.0, latency_ms=10.0)

    assert quote.active_id == 76
    assert quote.provider_name == "EURUSD-OTC"
    assert quote.ticker == "EURUSD"
    assert quote.is_otc is True
    assert quote.price == 1.12345
    assert quote.bid == 1.12344
    assert quote.ask == 1.12346
    assert quote.payout_turbo_pct == 85.0
    assert quote.payout_binary_pct == 86.0
    assert quote.session_open == 1.10
    assert quote.session_close == 1.13
    assert quote.received_at == 123.0
    assert quote.latency_ms == 10.0


def test_quote_uses_mid_if_price_missing():
    item = {
        "id": 1857,
        "ticker": "XAU",
        "providerName": "XAUUSD-OTC",
        "isOTC": True,
        "price": None,
        "quotation": {"bid": 3970.0, "ask": 3972.0},
    }
    quote = IQActiveQuote.from_graphql(item, received_at=1.0, latency_ms=1.0)
    assert quote.price == 3971.0


def test_quote_without_price_raises():
    item = {"id": 76, "ticker": "EURUSD", "isOTC": True, "price": None}
    with pytest.raises(ValueError):
        IQActiveQuote.from_graphql(item, received_at=1.0, latency_ms=1.0)


def test_client_sends_active_ids_and_parses():
    fake_session = _FakeSession(
        _FakeHttpResponse(
            {
                "data": {
                    "actives": [
                        {
                            "id": 76,
                            "ticker": "EURUSD",
                            "providerName": "EURUSD-OTC",
                            "isOTC": True,
                            "price": 1.1200,
                            "quotation": {"bid": 1.1199, "ask": 1.1201},
                            "payoutTurbo": 85,
                            "payoutBinary": 86,
                            "sessionStat": {"open": 1.1, "close": 1.13},
                        }
                    ]
                }
            }
        )
    )
    client = IQPublicClient(retries=0, session=fake_session)
    quotes = client.fetch_actives([76, 76, 1857])

    assert len(quotes) == 1
    assert quotes[0].provider_name == "EURUSD-OTC"
    captured = fake_session.calls[0]
    assert captured["json"]["variables"] == {"ids": [76, 1857]}
    assert "[ActiveID!]!" in captured["json"]["query"]
    assert captured["url"] == "https://api.iqoption.com/v1/fininfo/graphql"
    assert captured["timeout"] == 20.0


def test_client_raises_on_graphql_errors():
    fake_session = _FakeSession(
        _FakeHttpResponse({"data": None, "errors": [{"message": "boom"}]})
    )
    with pytest.raises(IQPublicError, match="boom"):
        IQPublicClient(retries=0, session=fake_session).fetch_actives([76])


def test_client_raises_without_valid_quotes():
    fake_session = _FakeSession(_FakeHttpResponse({"data": {"actives": []}}))
    with pytest.raises(IQPublicError, match="cotizaciones válidas"):
        IQPublicClient(retries=0, session=fake_session).fetch_actives([76])


def test_fetch_charts_parsea_ordena_y_deduplica():
    fake_session = _FakeSession(
        _FakeHttpResponse(
            {
                "data": {
                    "actives": [
                        {
                            "id": 76,
                            "providerName": "EURUSD-OTC",
                            "charts": {
                                "d1": {
                                    "quotes": [
                                        {"timestamp": BASE + 120, "price": 1.12},
                                        {"timestamp": BASE, "price": 1.10},
                                        {"timestamp": BASE + 120, "price": 1.125},
                                        {"timestamp": BASE + 60, "price": 0},
                                        {"timestamp": None, "price": 1.11},
                                    ]
                                }
                            },
                        },
                        {
                            "id": 1857,
                            "providerName": "XAUUSD-OTC",
                            "charts": {"d1": {"quotes": []}},
                        },
                    ]
                }
            }
        )
    )
    client = IQPublicClient(retries=0, session=fake_session)
    charts = client.fetch_charts([76, 1857], period="d1")

    assert len(charts) == 1
    assert charts[0].active_id == 76
    assert charts[0].period == "d1"
    assert [q.timestamp for q in charts[0].quotes] == [BASE, BASE + 120]
    assert charts[0].quotes[-1].price == 1.125
    captured = fake_session.calls[0]
    assert captured["json"]["variables"] == {"ids": [76, 1857]}
    assert "charts" in captured["json"]["query"]
    assert "d1" in captured["json"]["query"]


def test_fetch_charts_rechaza_periodo_desconocido():
    client = IQPublicClient(retries=0, session=_FakeSession(_FakeHttpResponse({})))
    with pytest.raises(ValueError, match="Período"):
        client.fetch_charts([76], period="h4")
