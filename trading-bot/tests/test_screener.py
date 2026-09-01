from common import config
from short_term import screener


class _FakeBroker:
    def __init__(self, tradable, liquidity):
        self._tradable = tradable
        self._liquidity = liquidity

    def list_tradable_symbols(self):
        return self._tradable

    def liquidity_snapshot(self, symbols, batch_size=200):
        return {s: self._liquidity[s] for s in symbols if s in self._liquidity}


def test_build_full_market_universe_filters_by_price_and_volume(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_MIN_PRICE_FULL_MARKET", 10.0)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_DOLLAR_VOLUME", 1_000_000.0)
    monkeypatch.setattr(config, "SHORT_TERM_FULL_MARKET_MAX_SYMBOLS", 100)

    tradable = ["AAA", "PENNY", "ILLIQUID", "BBB"]
    liquidity = {
        "AAA": {"price": 50.0, "dollar_volume": 5_000_000.0},
        "PENNY": {"price": 2.0, "dollar_volume": 3_000_000.0},  # sotto la soglia di prezzo
        "ILLIQUID": {"price": 40.0, "dollar_volume": 100_000.0},  # sotto la soglia di volume$
        "BBB": {"price": 20.0, "dollar_volume": 2_000_000.0},
    }
    broker = _FakeBroker(tradable, liquidity)

    result = screener.build_full_market_universe(broker)

    assert result == ["AAA", "BBB"]  # ordinati per volume$ decrescente, penny/illiquid esclusi


def test_build_full_market_universe_caps_to_max_symbols(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_MIN_PRICE_FULL_MARKET", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_DOLLAR_VOLUME", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_FULL_MARKET_MAX_SYMBOLS", 2)

    tradable = ["LOW", "MID", "HIGH"]
    liquidity = {
        "LOW": {"price": 20.0, "dollar_volume": 1.0},
        "MID": {"price": 20.0, "dollar_volume": 2.0},
        "HIGH": {"price": 20.0, "dollar_volume": 3.0},
    }
    broker = _FakeBroker(tradable, liquidity)

    result = screener.build_full_market_universe(broker)

    assert result == ["HIGH", "MID"]


def test_screen_universe_uses_full_market_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_USE_FULL_MARKET", True)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_PRICE_FULL_MARKET", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_DOLLAR_VOLUME", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_FULL_MARKET_MAX_SYMBOLS", 10)

    broker = _FakeBroker(["ZZZ"], {"ZZZ": {"price": 15.0, "dollar_volume": 10.0}})
    scanned: list[str] = []
    monkeypatch.setattr(screener, "scan_symbol", lambda symbol, *a, **k: scanned.append(symbol) or [])
    monkeypatch.setattr(screener, "get_daily_bars", lambda symbol, period="1y": _empty_bars())

    screener.screen_universe(broker=broker)

    assert scanned == ["ZZZ"]


def test_screen_universe_ignores_full_market_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_USE_FULL_MARKET", False)
    scanned: list[str] = []
    monkeypatch.setattr(screener, "scan_symbol", lambda symbol, *a, **k: scanned.append(symbol) or [])
    monkeypatch.setattr(screener, "get_daily_bars", lambda symbol, period="1y": _empty_bars())

    screener.screen_universe(symbols=["AAPL"])

    assert scanned == ["AAPL"]


def _empty_bars():
    import pandas as pd

    return pd.DataFrame({"open": [], "high": [], "low": [], "close": [], "volume": []})
