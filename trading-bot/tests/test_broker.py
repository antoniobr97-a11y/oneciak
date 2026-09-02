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
