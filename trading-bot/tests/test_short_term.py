import numpy as np
import pandas as pd

from short_term import levels, money_management, patterns, trend


def _make_df(highs, lows, closes, opens=None):
    n = len(closes)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    opens = opens if opens is not None else closes
    return pd.DataFrame(
        {
            "open": pd.Series(opens, index=idx, dtype=float),
            "high": pd.Series(highs, index=idx, dtype=float),
            "low": pd.Series(lows, index=idx, dtype=float),
            "close": pd.Series(closes, index=idx, dtype=float),
            "volume": np.full(n, 1_000_000),
        },
        index=idx,
    )


# --- money_management --------------------------------------------------

def test_position_size_basic_formula():
    # rischio 1% di 10.000 = 100; rischio/az = 5 -> 20 azioni
    qty = money_management.position_size(10_000, risk_pct=1.0, risk_per_share=5.0)
    assert qty == 20


def test_position_size_zero_risk_per_share():
    assert money_management.position_size(10_000, risk_pct=1.0, risk_per_share=0.0) == 0


def test_position_size_fx_rate():
    # rischio_per_azione espresso in USD, cambio 0.9 EUR per USD
    qty_no_fx = money_management.position_size(10_000, 1.0, 10.0, fx_rate=1.0)
    qty_fx = money_management.position_size(10_000, 1.0, 10.0, fx_rate=0.9)
    assert qty_fx != qty_no_fx


def test_aggregate_risk_cap_boundary():
    assert money_management.can_open_new_position(11, risk_pct_per_trade=1.0)  # 12% <= 12%
    assert not money_management.can_open_new_position(12, risk_pct_per_trade=1.0)  # 13% > 12%


def test_drawdown_recovery_matches_known_values():
    assert abs(money_management.drawdown_recovery_pct(20) - 25.0) < 1e-6
    assert abs(money_management.drawdown_recovery_pct(50) - 100.0) < 1e-6
    assert abs(money_management.drawdown_recovery_pct(70) - 233.333333) < 1e-3


def test_profit_factor():
    assert money_management.profit_factor([100, -50, 50, -25]) == (150 / 75)
    assert money_management.profit_factor([100, 50]) == float("inf")
    assert money_management.profit_factor([]) == 0.0


# --- levels --------------------------------------------------------------

def test_compute_levels_long_outside_setup_bar_range():
    setup_bar = pd.Series({"open": 100, "high": 102, "low": 98, "close": 101})
    result = levels.compute_levels(setup_bar, volatility=3.0, direction="long")
    assert result.entry == 104.0  # 101 + 3, already above the high (102)
    assert result.stop_loss == 95.0  # 98 - 3
    assert result.risk_per_share == 9.0


def test_compute_levels_long_entry_inside_bar_range_gets_pushed_above_high():
    setup_bar = pd.Series({"open": 100, "high": 110, "low": 98, "close": 101})
    result = levels.compute_levels(setup_bar, volatility=3.0, direction="long")
    # 101 + 3 = 104, which falls inside [98, 110] -> pushed just above the high
    assert result.entry > 110


def test_compute_levels_short_is_mirror_of_long():
    setup_bar = pd.Series({"open": 100, "high": 102, "low": 98, "close": 99})
    result = levels.compute_levels(setup_bar, volatility=3.0, direction="short")
    assert result.entry == 96.0  # 99 - 3
    assert result.stop_loss == 105.0  # 102 + 3


def test_reached_1r_and_breakeven():
    assert levels.reached_1r(current_price=110, entry=100, stop_loss=95)  # risk=5, +1R=105 <= 110
    assert not levels.reached_1r(current_price=103, entry=100, stop_loss=95)
    assert levels.breakeven_stop(100) == 100


def test_r_multiple_short_direction():
    # short: entry 100, stop 105 (risk=5) -> price at 95 is +1R
    assert abs(levels.r_multiple(95, entry=100, stop_loss=105) - 1.0) < 1e-9


# --- trend qualifiers ------------------------------------------------------

def test_performance_qualifier_detects_strong_uptrend():
    n = 60
    closes = np.linspace(100, 140, n)  # +40% low to high
    df = _make_df(closes * 1.005, closes * 0.995, closes)
    assert trend.performance_qualifier(df, "long", lookback=60)
    assert not trend.performance_qualifier(df, "short", lookback=60)


def test_gap_qualifier_detects_up_gap():
    n = 30
    closes = [100.0] * n
    opens = list(closes)
    opens[15] = closes[14] * 1.02  # 2% gap up, above the 1% threshold
    df = _make_df([o * 1.001 for o in opens], [o * 0.999 for o in opens], closes, opens=opens)
    assert trend.gap_qualifier(df, "long", lookback=30)


def test_adx_qualifier_true_on_strong_persistent_trend():
    n = 60
    closes = np.linspace(100, 200, n)  # very strong, clean uptrend
    highs = closes + 1
    lows = closes - 1
    df = _make_df(highs, lows, closes)
    assert trend.adx_qualifier(df)


# --- patterns --------------------------------------------------------------

def test_detect_pullback_semplice_long():
    # Rally to a new period high, then 4 bars of lower highs / lower lows.
    rally = list(np.linspace(100, 130, 40))
    pullback_highs = [128, 126, 124, 122]
    pullback_lows = [124, 122, 120, 118]
    highs = rally + pullback_highs
    lows = [c - 1 for c in rally] + pullback_lows
    closes = rally + [123, 121, 119, 117]
    df = _make_df(highs, lows, closes)

    match = patterns.detect_pullback_semplice(df, "long")
    assert match is not None
    assert match.pattern == "Pullback Semplice"
    assert 2 <= match.pullback_bar_count <= 7


def test_detect_tko_long():
    rally = list(np.linspace(100, 130, 40))
    highs = rally + [128]
    lows = [c - 1 for c in rally] + [110]  # wide-range sell-off bar breaking recent lows
    closes = rally + [111]
    df = _make_df(highs, lows, closes)

    match = patterns.detect_tko(df, "long")
    assert match is not None
    assert match.pattern == "TKO"


def test_detect_bowai_long_reversal():
    # ~7 months of decline (bearish MA order: SMA10 < EMA20 < EMA30), then a
    # sharp jump in the last few bars that flips the order to
    # SMA10 > EMA20 > EMA30 within the <=5-day inversion window.
    decline = np.linspace(150, 100, 145)
    jump = np.full(5, 300.0)
    closes = np.concatenate([decline, jump])
    df = _make_df(closes + 1, closes - 1, closes)

    match = patterns.detect_bowai(df, "long")
    assert match is not None
    assert match.pattern == "Bowai"


def test_detect_pullback_semplice_returns_none_without_pullback():
    closes = list(np.linspace(100, 130, 40))
    df = _make_df([c + 1 for c in closes], [c - 1 for c in closes], closes)
    assert patterns.detect_pullback_semplice(df, "long") is None


# --- regressioni trovate con lo stress-test su dati sintetici -------------

def test_harmony_qualifier_flat_market_qualifies_neither_direction():
    # Bug: un mercato piatto (tutti i valori uguali) faceva risultare vera
    # l'armonia "short", perché "not (b > a)" include erroneamente il
    # pareggio (b == a) nel conteggio "discendente".
    n = 60
    closes = [100.0] * n
    df = _make_df(closes, closes, closes)
    assert trend.harmony_qualifier(df, "long", lookback=60) is False
    assert trend.harmony_qualifier(df, "short", lookback=60) is False


def test_mostly_monotonic_treats_ties_as_neither_direction():
    assert trend._mostly_monotonic([1, 1, 1, 1, 1], rising=True) is False
    assert trend._mostly_monotonic([1, 1, 1, 1, 1], rising=False) is False
    assert trend._mostly_monotonic([1, 2, 3, 4, 5], rising=True) is True
    assert trend._mostly_monotonic([5, 4, 3, 2, 1], rising=False) is True


def test_persistence_qualifier_direction_aware():
    # Bug: persistence_qualifier non controllava il segno della pendenza,
    # quindi in un downtrend risultava vera per "long" (e in un mercato
    # piatto risultava vera per entrambe le direzioni, per pura bontà di
    # adattamento di una retta orizzontale).
    n = 40
    closes = np.linspace(150, 100, n)  # downtrend netto
    df = _make_df(closes + 1, closes - 1, closes)
    assert trend.persistence_qualifier(df, "short", window=20) is True
    assert trend.persistence_qualifier(df, "long", window=20) is False


def test_persistence_qualifier_rejects_flat_market():
    n = 40
    closes = [100.0] * n
    df = _make_df(closes, closes, closes)
    assert trend.persistence_qualifier(df, "long", window=20) is False
    assert trend.persistence_qualifier(df, "short", window=20) is False


# --- edge case: dati insufficienti / degeneri -----------------------------

def test_qualify_trend_short_history_does_not_crash():
    df = _make_df([101, 102, 103], [99, 100, 101], [100, 101, 102])
    result = trend.qualify_trend(df, "long")
    assert result.qualifies is False


def test_qualify_trend_empty_after_window_does_not_crash():
    df = _make_df([], [], [])
    result = trend.qualify_trend(df, "long")
    assert result.score == 0


def test_detect_all_patterns_tiny_df_returns_empty_list():
    df = _make_df([101, 102], [99, 100], [100, 101])
    assert patterns.detect_all(df, "long") == []
    assert patterns.detect_all(df, "short") == []


def test_compute_levels_flat_bar_nonzero_risk():
    # Su una barra completamente piatta (high==low==close) e volatilità
    # zero, l'entrata coincide col massimo -> viene spostata 1 cent sopra
    # (regola "se cade dentro/sul range, sposta appena sopra il massimo"),
    # quindi il rischio non è mai esattamente zero (eviterebbe una size
    # infinita in money_management).
    setup_bar = pd.Series({"open": 100, "high": 100, "low": 100, "close": 100})
    result = levels.compute_levels(setup_bar, volatility=0.0, direction="long")
    assert result.risk_per_share > 0.0


def test_position_size_negative_capital_returns_zero():
    assert money_management.position_size(-1000, risk_pct=1.0, risk_per_share=5.0) == 0


def test_position_size_negative_risk_per_share_returns_zero():
    assert money_management.position_size(10_000, risk_pct=1.0, risk_per_share=-5.0) == 0


def test_adx_qualifier_insufficient_history_returns_false():
    closes = [100, 101, 99, 102, 100]
    df = _make_df([c + 1 for c in closes], [c - 1 for c in closes], closes)
    assert trend.adx_qualifier(df) is False


def test_gap_qualifier_no_gaps_returns_false():
    n = 30
    closes = [100.0 + i * 0.01 for i in range(n)]  # no real gaps, tiny drift
    df = _make_df([c + 0.1 for c in closes], [c - 0.1 for c in closes], closes)
    assert trend.gap_qualifier(df, "long", lookback=30) is False
    assert trend.gap_qualifier(df, "short", lookback=30) is False


# --- swing point: picchi e valli non vanno mescolati ------------------------
# Bug reale: la versione precedente restituiva i punti che erano massimo
# OPPURE minimo della finestra. Chi chiedeva "i massimi sono crescenti?"
# riceveva una sequenza picco-valle-picco-valle, quindi non crescente quasi
# mai. Conseguenza misurata: harmony_qualifier sempre falso (uno dei 6
# qualificatori del corso, morto) e divergence_check che confrontava un
# picco con una valle.

def _wave(cycles=14, rise=60, n=80, amp=6):
    import numpy as np
    import pandas as pd

    close = np.linspace(100, 100 + rise, n) + amp * np.sin(np.linspace(0, cycles * np.pi, n))
    return pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": [1e6] * n},
        index=pd.date_range("2025-01-01", periods=n, freq="B"),
    )


def test_swing_points_returns_only_peaks_or_only_troughs():
    from short_term.indicators import swing_points

    df = _wave()
    peaks = [v for _, v in swing_points(df["high"], order=2, kind="high")]
    troughs = [v for _, v in swing_points(df["low"], order=2, kind="low")]

    assert len(peaks) >= 4 and len(troughs) >= 4
    # in un rialzo regolare i picchi crescono, e cosi' le valli
    assert peaks == sorted(peaks)
    assert troughs == sorted(troughs)
    # nessun picco coincide con una valle: le due liste sono davvero distinte
    assert not set(peaks) & set(troughs)


def test_swing_points_rejects_an_unknown_kind():
    import pytest

    from short_term.indicators import swing_points

    with pytest.raises(ValueError):
        swing_points(_wave()["high"], kind="entrambi")


def test_harmony_qualifier_recognises_a_textbook_uptrend():
    from short_term.trend import harmony_qualifier

    up = _wave()
    assert harmony_qualifier(up, "long", 60) is True
    assert harmony_qualifier(up, "short", 60) is False


def test_harmony_qualifier_recognises_a_textbook_downtrend():
    from short_term.trend import harmony_qualifier

    down = _wave(rise=-60)
    assert harmony_qualifier(down, "short", 60) is True
    assert harmony_qualifier(down, "long", 60) is False
