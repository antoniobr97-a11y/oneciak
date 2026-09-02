from unittest.mock import MagicMock

import pytest

from common import config
from common.broker import Broker


class _FakeBar:
    def __init__(self, close):
        self.close = close


class _FakeBarSet(dict):
    def __getitem__(self, symbol):
        return dict.__getitem__(self, symbol)


class _FakeDataClient:
    def __init__(self, bars_by_symbol):
        self._bars_by_symbol = bars_by_symbol

    def get_stock_bars(self, request):
        requested = set(request.symbol_or_symbols)
        return _FakeBarSet({s: self._bars_by_symbol[s] for s in requested if s in self._bars_by_symbol})


def _make_broker(monkeypatch, bars_by_symbol):
    monkeypatch.setattr(config, "ALPACA_API_KEY", "test_key")
    monkeypatch.setattr(config, "ALPACA_SECRET_KEY", "test_secret")
    broker = Broker()
    broker.data_client = _FakeDataClient(bars_by_symbol)
    return broker


def test_volatility_snapshot_computes_annualized_stdev(monkeypatch):
    # Rendimenti giornalieri costanti +1% -> deviazione standard 0 -> vol 0.
    closes = [100.0]
    for _ in range(10):
        closes.append(closes[-1] * 1.01)
    broker = _make_broker(monkeypatch, {"FLAT": [_FakeBar(c) for c in closes]})

    result = broker.volatility_snapshot(["FLAT"])

    assert result["FLAT"] == pytest.approx(0.0, abs=1e-9)


def test_volatility_snapshot_higher_for_more_volatile_series(monkeypatch):
    calm = [100.0, 101.0, 100.0, 101.0, 100.0, 101.0, 100.0]
    wild = [100.0, 120.0, 90.0, 130.0, 80.0, 140.0, 70.0]
    broker = _make_broker(
        monkeypatch,
        {"CALM": [_FakeBar(c) for c in calm], "WILD": [_FakeBar(c) for c in wild]},
    )

    result = broker.volatility_snapshot(["CALM", "WILD"])

    assert result["WILD"] > result["CALM"]


def test_volatility_snapshot_skips_symbols_with_too_few_bars(monkeypatch):
    broker = _make_broker(monkeypatch, {"THIN": [_FakeBar(100.0), _FakeBar(101.0)]})

    result = broker.volatility_snapshot(["THIN"])

    assert "THIN" not in result


def test_volatility_snapshot_skips_symbols_missing_from_response(monkeypatch):
    broker = _make_broker(monkeypatch, {})

    result = broker.volatility_snapshot(["MISSING"])

    assert result == {}


# --- audit: ordine delle operazioni sugli stop ---------------------------------

def _stop_order(order_id="stop-1"):
    o = MagicMock()
    o.id = order_id
    o.order_type = "stop"
    return o


def _broker_with_client(monkeypatch, open_orders):
    monkeypatch.setattr(config, "ALPACA_API_KEY", "test_key")
    monkeypatch.setattr(config, "ALPACA_SECRET_KEY", "test_secret")
    broker = Broker()
    client = MagicMock()
    client.get_orders.return_value = open_orders
    broker.client = client
    return broker, client


def test_close_partial_cancels_open_stop_before_submitting(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [_stop_order()])

    broker.close_partial("AAPL", 5, "long")

    names = [c[0] for c in client.method_calls if c[0] in ("cancel_order_by_id", "submit_order")]
    assert names == ["cancel_order_by_id", "submit_order"]


def test_flatten_cancels_open_stops_before_closing(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [_stop_order("a"), _stop_order("b")])

    broker.flatten("AAPL")

    names = [c[0] for c in client.method_calls if c[0] in ("cancel_order_by_id", "close_position")]
    assert names == ["cancel_order_by_id", "cancel_order_by_id", "close_position"]


def test_place_stop_replaces_existing_stop_with_gtc(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [_stop_order()])

    broker.place_stop("AAPL", 5, 100.0, "long")

    client.cancel_order_by_id.assert_called_once_with("stop-1")
    submitted = client.submit_order.call_args[0][0]
    assert str(submitted.time_in_force).lower().endswith("gtc")
    assert submitted.qty == 5 and submitted.stop_price == 100.0


def test_enter_with_stop_uses_gtc_so_the_stop_leg_survives_the_day(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [])

    broker.enter_with_stop("AAPL", 10, "long", 95.0)

    submitted = client.submit_order.call_args[0][0]
    assert str(submitted.time_in_force).lower().endswith("gtc")
    assert submitted.stop_loss.stop_price == 95.0
