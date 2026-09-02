"""Fedelta' al corso (video 29/32/33): minimi E massimi decrescenti nel
pullback semplice; stop sotto il minimo piu' basso del pullback per Trend
Pivot e Second Entry (barra diversa da quella di entrata)."""
import numpy as np
import pandas as pd

from short_term import levels, patterns


def _bars(rows):
    """rows: lista di (open, high, low, close). Volume costante."""
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="B")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 1_000_000
    return df


def _uptrend_then(pullback_rows):
    # 40 barre di trend rialzista pulito, poi il picco, poi il pullback dato
    trend = [(100 + i, 101.5 + i, 99.5 + i, 101 + i) for i in range(40)]
    peak = [(141, 143, 140.5, 142.5)]
    return _bars(trend + peak + pullback_rows)


def test_pullback_semplice_requires_decreasing_lows_too():
    # massimi decrescenti ma minimi NON decrescenti (la seconda barra ha un minimo piu' alto)
    bad = _uptrend_then([(142, 142.5, 139.0, 139.5), (140, 141.5, 139.8, 140.0), (140, 140.8, 139.6, 139.9)])
    assert patterns.detect_pullback_semplice(bad, "long", lookback=60) is None

    # massimi E minimi decrescenti barra dopo barra
    good = _uptrend_then([(142, 142.5, 139.5, 140.0), (140, 141.5, 138.8, 139.2), (139, 140.5, 138.0, 138.5)])
    match = patterns.detect_pullback_semplice(good, "long", lookback=60)
    assert match is not None and match.pattern == "Pullback Semplice"
    assert match.stop_bar_index is None  # stessa barra per entrata e stop


def test_second_entry_stop_refers_to_deepest_pullback_bar():
    # pullback: barra 1 profonda (minimo 136), barra 2 = breakout fallito (supera il massimo
    # precedente ma chiude sotto) con minimo piu' alto (138) -> entrata sulla barra 2,
    # stop sotto il minimo della barra 1
    df = _uptrend_then([(142, 142.5, 136.0, 137.0), (137, 143.0, 138.0, 139.0)])
    match = patterns.detect_second_entry_pullback(df, "long", lookback=60)
    assert match is not None
    setup, stop_bar = match.setup_bar_index, match.stop_bar_index
    assert setup == len(df) - 1
    assert stop_bar == len(df) - 2
    assert float(df["low"].iloc[stop_bar]) == 136.0

    lv = levels.levels_for_setup_bar(df, setup, "long", stop_bar_index=stop_bar)
    lv_same_bar = levels.levels_for_setup_bar(df, setup, "long")
    assert lv.entry == lv_same_bar.entry  # l'entrata non cambia
    assert lv.stop_loss < lv_same_bar.stop_loss  # lo stop e' sotto il minimo piu' basso del pullback
    assert lv.risk_per_share > lv_same_bar.risk_per_share


def test_trend_pivot_enters_above_pivot_bar_and_stops_below_pullback_low():
    # a: minimo 138 ; b (pivot): massimo piu' alto dei vicini ; c: fallisce, minimo 136 (< a)
    df = _uptrend_then([(141, 141.5, 138.0, 139.0), (139, 142.0, 138.5, 139.5), (139, 140.0, 136.0, 137.0)])
    match = patterns.detect_trend_pivot_pullback(df, "long", lookback=60)
    assert match is not None
    b, c = len(df) - 2, len(df) - 1
    assert match.setup_bar_index == b
    assert match.stop_bar_index == c


def test_compute_levels_with_separate_stop_bar_short():
    setup = pd.Series({"open": 50.0, "high": 51.0, "low": 49.0, "close": 49.5})
    stop_bar = pd.Series({"open": 52.0, "high": 54.0, "low": 51.0, "close": 51.5})
    lv = levels.compute_levels(setup, volatility=1.0, direction="short", stop_bar=stop_bar)
    assert lv.entry == 48.5  # chiusura - volatilita' (fuori dal range: ok)
    assert lv.stop_loss == 55.0  # massimo della barra di stop + volatilita'
    assert np.isclose(lv.risk_per_share, 6.5)
