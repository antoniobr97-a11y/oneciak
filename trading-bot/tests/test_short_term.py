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
