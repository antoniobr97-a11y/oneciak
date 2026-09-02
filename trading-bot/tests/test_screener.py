from common import config
from short_term import screener


class _FakeBroker:
    def __init__(self, tradable, liquidity, volatility=None):
        self._tradable = tradable
        self._liquidity = liquidity
        self._volatility = volatility or {}

    def list_tradable_symbols(self):
        return self._tradable

    def liquidity_snapshot(self, symbols, batch_size=200):
        return {s: self._liquidity[s] for s in symbols if s in self._liquidity}

    def volatility_snapshot(self, symbols, lookback_days=30, batch_size=200):
        return {s: self._volatility[s] for s in symbols if s in self._volatility}


def test_build_full_market_universe_filters_by_price_and_volume(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_MIN_PRICE_FULL_MARKET", 10.0)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_DOLLAR_VOLUME", 1_000_000.0)
    monkeypatch.setattr(config, "SHORT_TERM_FULL_MARKET_MAX_SYMBOLS", 100)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_ANNUALIZED_VOLATILITY_PCT", 0.0)

    tradable = ["AAA", "PENNY", "ILLIQUID", "BBB"]
    liquidity = {
        "AAA": {"price": 50.0, "volume": 1_000_000.0, "dollar_volume":5_000_000.0},
        "PENNY": {"price": 2.0, "volume": 1_000_000.0, "dollar_volume":3_000_000.0},  # sotto la soglia di prezzo
        "ILLIQUID": {"price": 40.0, "volume": 1_000_000.0, "dollar_volume":100_000.0},  # sotto la soglia di volume$
        "BBB": {"price": 20.0, "volume": 1_000_000.0, "dollar_volume":2_000_000.0},
    }
    broker = _FakeBroker(tradable, liquidity)

    result = screener.build_full_market_universe(broker)

    assert result == ["AAA", "BBB"]  # ordinati per volume$ decrescente, penny/illiquid esclusi


def test_build_full_market_universe_filters_by_share_volume(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_MIN_PRICE_FULL_MARKET", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_DOLLAR_VOLUME", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_SHARE_VOLUME", 100_000.0)  # corso: >100k pezzi/giorno
    monkeypatch.setattr(config, "SHORT_TERM_FULL_MARKET_MAX_SYMBOLS", 100)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_ANNUALIZED_VOLATILITY_PCT", 0.0)

    liquidity = {
        "THIN": {"price": 500.0, "volume": 20_000.0, "dollar_volume": 10_000_000.0},  # tanti $, pochi pezzi
        "OK": {"price": 20.0, "volume": 500_000.0, "dollar_volume": 10_000_000.0},
    }
    broker = _FakeBroker(["THIN", "OK"], liquidity)

    assert screener.build_full_market_universe(broker) == ["OK"]


def test_build_full_market_universe_caps_to_max_symbols(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_MIN_PRICE_FULL_MARKET", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_DOLLAR_VOLUME", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_FULL_MARKET_MAX_SYMBOLS", 2)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_ANNUALIZED_VOLATILITY_PCT", 0.0)

    tradable = ["LOW", "MID", "HIGH"]
    liquidity = {
        "LOW": {"price": 20.0, "volume": 1_000_000.0, "dollar_volume":1.0},
        "MID": {"price": 20.0, "volume": 1_000_000.0, "dollar_volume":2.0},
        "HIGH": {"price": 20.0, "volume": 1_000_000.0, "dollar_volume":3.0},
    }
    broker = _FakeBroker(tradable, liquidity)

    result = screener.build_full_market_universe(broker)

    assert result == ["HIGH", "MID"]


def test_build_full_market_universe_filters_by_volatility(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_MIN_PRICE_FULL_MARKET", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_DOLLAR_VOLUME", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_FULL_MARKET_MAX_SYMBOLS", 100)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_ANNUALIZED_VOLATILITY_PCT", 25.0)

    tradable = ["FLAT", "TRENDY"]
    liquidity = {
        "FLAT": {"price": 50.0, "volume": 1_000_000.0, "dollar_volume":5_000_000.0},
        "TRENDY": {"price": 50.0, "volume": 1_000_000.0, "dollar_volume":1_000_000.0},
    }
    volatility = {"FLAT": 0.10, "TRENDY": 0.40}  # 10% e 40% annualizzata
    broker = _FakeBroker(tradable, liquidity, volatility)

    result = screener.build_full_market_universe(broker)

    assert result == ["TRENDY"]  # FLAT sotto la soglia di volatilita', escluso pur avendo piu' volume$


def test_build_full_market_universe_missing_volatility_data_excludes_symbol(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_MIN_PRICE_FULL_MARKET", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_DOLLAR_VOLUME", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_FULL_MARKET_MAX_SYMBOLS", 100)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_ANNUALIZED_VOLATILITY_PCT", 25.0)

    tradable = ["NODATA"]
    liquidity = {"NODATA": {"price": 50.0, "volume": 1_000_000.0, "dollar_volume":5_000_000.0}}
    broker = _FakeBroker(tradable, liquidity, volatility={})  # nessun dato di volatilita'

    result = screener.build_full_market_universe(broker)

    assert result == []


def test_screen_universe_uses_full_market_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_USE_FULL_MARKET", True)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_PRICE_FULL_MARKET", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_DOLLAR_VOLUME", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_FULL_MARKET_MAX_SYMBOLS", 10)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_ANNUALIZED_VOLATILITY_PCT", 0.0)

    broker = _FakeBroker(["ZZZ"], {"ZZZ": {"price": 15.0, "volume": 1_000_000.0, "dollar_volume":10.0}})
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


# --- filtro di regime di mercato (v5) -----------------------------------------

def _index_bars(closes):
    import pandas as pd

    s = pd.Series(closes, dtype=float)
    return pd.DataFrame({"open": s, "high": s, "low": s, "close": s, "volume": 1.0})


def test_allowed_directions_long_only_in_bull_regime(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_ALLOW_SHORTS", True)
    monkeypatch.setattr(config, "MARKET_REGIME_FILTER", True)
    monkeypatch.setattr(config, "MARKET_REGIME_MA_PERIOD", 200)
    assert screener.allowed_directions(_index_bars(range(100, 400))) == ("long",)


def test_allowed_directions_short_only_in_bear_regime_when_shorts_enabled(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_ALLOW_SHORTS", True)
    monkeypatch.setattr(config, "MARKET_REGIME_FILTER", True)
    monkeypatch.setattr(config, "MARKET_REGIME_MA_PERIOD", 200)
    assert screener.allowed_directions(_index_bars(range(400, 100, -1))) == ("short",)


def test_allowed_directions_both_when_filter_disabled_and_shorts_enabled(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_ALLOW_SHORTS", True)
    monkeypatch.setattr(config, "MARKET_REGIME_FILTER", False)
    assert screener.allowed_directions(_index_bars(range(100, 400))) == ("long", "short")


def test_allowed_directions_both_without_enough_history(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_ALLOW_SHORTS", True)
    monkeypatch.setattr(config, "MARKET_REGIME_FILTER", True)
    monkeypatch.setattr(config, "MARKET_REGIME_MA_PERIOD", 200)
    assert screener.allowed_directions(_index_bars(range(100, 150))) == ("long", "short")


def test_allowed_directions_default_never_shorts(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_ALLOW_SHORTS", False)
    monkeypatch.setattr(config, "MARKET_REGIME_FILTER", False)
    assert screener.allowed_directions(_index_bars(range(400, 100, -1))) == ("long",)


def test_allowed_directions_empty_in_bear_regime_without_shorts(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_ALLOW_SHORTS", False)
    monkeypatch.setattr(config, "MARKET_REGIME_FILTER", True)
    monkeypatch.setattr(config, "MARKET_REGIME_MA_PERIOD", 200)
    assert screener.allowed_directions(_index_bars(range(400, 100, -1))) == ()


def test_screen_universe_passes_regime_directions_to_scan(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_USE_FULL_MARKET", False)
    monkeypatch.setattr(config, "SHORT_TERM_ALLOW_SHORTS", True)
    monkeypatch.setattr(config, "MARKET_REGIME_FILTER", True)
    monkeypatch.setattr(config, "MARKET_REGIME_MA_PERIOD", 200)
    seen = {}
    monkeypatch.setattr(screener, "scan_symbol", lambda symbol, *a, **k: seen.setdefault(symbol, k.get("directions")) and [])
    monkeypatch.setattr(screener, "get_daily_bars", lambda symbol, period="1y": _index_bars(range(100, 400)))

    screener.screen_universe(symbols=["AAPL"])

    assert seen["AAPL"] == ("long",)


def test_screen_universe_scans_nothing_in_bear_regime_without_shorts(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_USE_FULL_MARKET", False)
    monkeypatch.setattr(config, "SHORT_TERM_ALLOW_SHORTS", False)
    monkeypatch.setattr(config, "MARKET_REGIME_FILTER", True)
    monkeypatch.setattr(config, "MARKET_REGIME_MA_PERIOD", 200)
    scanned = []
    monkeypatch.setattr(screener, "scan_symbol", lambda symbol, *a, **k: scanned.append(symbol) or [])
    monkeypatch.setattr(screener, "get_daily_bars", lambda symbol, period="1y": _index_bars(range(400, 100, -1)))

    assert screener.screen_universe(symbols=["AAPL"]) == []
    assert scanned == []
