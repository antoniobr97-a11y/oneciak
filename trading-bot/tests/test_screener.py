from unittest.mock import patch

import pytest

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


def test_missing_volatility_for_a_few_symbols_still_excludes_them(monkeypatch):
    """Copertura sufficiente (75%): chi non ha dati resta fuori, come prima."""
    monkeypatch.setattr(config, "SHORT_TERM_MIN_PRICE_FULL_MARKET", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_DOLLAR_VOLUME", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_FULL_MARKET_MAX_SYMBOLS", 100)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_ANNUALIZED_VOLATILITY_PCT", 25.0)

    tradable = ["A", "B", "C", "NODATA"]
    liquidity = {s: {"price": 50.0, "volume": 1_000_000.0, "dollar_volume": 5_000_000.0} for s in tradable}
    volatility = {"A": 0.40, "B": 0.35, "C": 0.30}
    broker = _FakeBroker(tradable, liquidity, volatility)

    assert screener.build_full_market_universe(broker) == ["A", "B", "C"]


def test_widespread_volatility_data_failure_skips_the_filter_and_alerts(monkeypatch):
    """Il guasto trovato al primo avvio reale: il feed dati rifiuta le
    richieste, nessuna volatilita' arriva, e il bot scartava TUTTO
    smettendo di operare in silenzio. Ora salta il filtro e segnala."""
    monkeypatch.setattr(config, "SHORT_TERM_MIN_PRICE_FULL_MARKET", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_DOLLAR_VOLUME", 0.0)
    monkeypatch.setattr(config, "SHORT_TERM_FULL_MARKET_MAX_SYMBOLS", 100)
    monkeypatch.setattr(config, "SHORT_TERM_MIN_ANNUALIZED_VOLATILITY_PCT", 25.0)

    tradable = ["A", "B", "C", "D"]
    liquidity = {s: {"price": 50.0, "volume": 1_000_000.0, "dollar_volume": 5_000_000.0} for s in tradable}
    broker = _FakeBroker(tradable, liquidity, volatility={})  # nessun dato: guasto

    with patch("short_term.screener.notify.alert") as alert:
        result = screener.build_full_market_universe(broker)

    assert sorted(result) == ["A", "B", "C", "D"], "un guasto sui dati non deve azzerare l'universo"
    assert any(kw.get("level") == "error" for _, kw in alert.call_args_list), "il guasto va segnalato"


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


# --- priorita' ai candidati vicini all'estremo a 52 settimane (v9) ----------

def _closes(values):
    import pandas as pd

    idx = pd.date_range("2024-01-01", periods=len(values), freq="B")
    return pd.DataFrame({"close": pd.Series(values, dtype=float, index=idx)})


def test_proximity_long_is_one_at_a_new_yearly_high():
    df = _closes(list(range(100, 400)))  # ultimo valore = massimo
    assert screener.proximity_to_52w_extreme(df, "long") == 1.0


def test_proximity_long_is_lower_far_from_the_high():
    df = _closes(list(range(100, 300)) + [200.0])  # massimo 299, ultimo 200
    assert screener.proximity_to_52w_extreme(df, "long") == pytest.approx(200 / 299, rel=1e-6)


def test_proximity_short_is_one_at_a_new_yearly_low():
    df = _closes(list(range(400, 100, -1)))  # ultimo valore = minimo
    assert screener.proximity_to_52w_extreme(df, "short") == 1.0


def test_proximity_uses_only_the_last_52_weeks():
    # un massimo vecchissimo (1000) fuori dalla finestra non deve contare
    df = _closes([1000.0] + [100.0] * 300)
    assert screener.proximity_to_52w_extreme(df, "long") == 1.0


def test_proximity_is_zero_without_enough_data():
    assert screener.proximity_to_52w_extreme(_closes([100.0]), "long") == 0.0


def _cand(symbol, proximity, score=3, risk=5.0, pattern="Pullback Semplice"):
    from short_term.levels import EntryLevels
    from short_term.trend import TrendQualification

    return screener.Candidate(
        symbol=symbol, direction="long", pattern=pattern,
        trend=TrendQualification(direction="long", score=score, satisfied={}),
        levels=EntryLevels(direction="long", entry=100.0, stop_loss=100.0 - risk, risk_per_share=risk),
        qty=10, ribbon_aligned=True, sector_etf="XLK", sector_passes=True,
        earnings_warn=False, sr_too_close=False, price_blocks_trade=False,
        has_divergence=False, proximity_52w=proximity,
    )


def test_dedupe_keeps_the_best_qualified_pattern_per_symbol():
    """Un titolo con piu' pattern e' una sola opportunita': senza deduplica
    il bot piazzerebbe un ordine e lo sostituirebbe subito con l'altro."""
    ranked = screener.rank_candidates([
        _cand("TEVA", 0.90, score=3, risk=3.63, pattern="TKO"),
        _cand("TEVA", 0.90, score=5, risk=2.33, pattern="Second Entry Pullback"),
    ])

    assert len(ranked) == 1
    assert ranked[0].pattern == "Second Entry Pullback"  # trend piu' qualificato


def test_dedupe_tie_on_score_prefers_the_tighter_stop():
    ranked = screener.rank_candidates([
        _cand("DGX", 0.90, score=4, risk=12.86, pattern="TKO"),
        _cand("DGX", 0.90, score=4, risk=6.40, pattern="Second Entry Pullback"),
    ])

    assert len(ranked) == 1
    assert ranked[0].levels.risk_per_share == 6.40


def test_rank_candidates_puts_the_closest_to_the_yearly_high_first():
    ranked = screener.rank_candidates([_cand("FAR", 0.70), _cand("NEAR", 0.99), _cand("MID", 0.85)])
    assert [c.symbol for c in ranked] == ["NEAR", "MID", "FAR"]


def test_screen_universe_returns_candidates_ranked(monkeypatch):
    monkeypatch.setattr(config, "SHORT_TERM_USE_FULL_MARKET", False)
    monkeypatch.setattr(config, "MARKET_REGIME_FILTER", False)
    by_symbol = {"LOW": [_cand("LOW", 0.60)], "HIGH": [_cand("HIGH", 0.98)]}
    monkeypatch.setattr(screener, "scan_symbol", lambda symbol, *a, **k: by_symbol[symbol])
    monkeypatch.setattr(screener, "get_daily_bars", lambda symbol, period="1y": _empty_bars())

    ranked = screener.screen_universe(symbols=["LOW", "HIGH"])

    assert [c.symbol for c in ranked] == ["HIGH", "LOW"]


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
