import numpy as np
import pandas as pd

from risk import position_size
from strategy import add_indicators, generate_signal


def _make_df(closes):
    n = len(closes)
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    closes = pd.Series(closes, index=idx, dtype=float)
    df = pd.DataFrame(
        {
            "open": closes,
            "high": closes * 1.01,
            "low": closes * 0.99,
            "close": closes,
            "volume": np.full(n, 1_000_000),
        },
        index=idx,
    )
    return df


def test_no_signal_without_enough_history():
    df = add_indicators(_make_df(np.linspace(100, 110, 30)))
    signal = generate_signal(df, has_open_position=False)
    assert signal.action == "HOLD"


def _first_crossover_index(df, direction):
    fast, slow = df["sma_fast"], df["sma_slow"]
    for i in range(1, len(df)):
        if fast.iloc[i - 1] is None or pd.isna(slow.iloc[i - 1]):
            continue
        if direction == "up" and fast.iloc[i - 1] <= slow.iloc[i - 1] and fast.iloc[i] > slow.iloc[i]:
            return i
        if direction == "down" and fast.iloc[i - 1] >= slow.iloc[i - 1] and fast.iloc[i] < slow.iloc[i]:
            return i
    raise AssertionError(f"no {direction} crossover found in fixture")


def test_buy_on_upward_crossover():
    # Noisy downtrend then noisy uptrend -- realistic enough that RSI
    # doesn't just spike to an immediate extreme, so the crossover and the
    # RSI filter can both plausibly line up.
    rng = np.random.default_rng(7)
    n = 90
    noise = rng.normal(0, 0.6, n)
    trend = np.concatenate([np.linspace(0, -3, 40), np.linspace(-3, 8, 50)])
    closes = 100 + trend + noise
    df = add_indicators(_make_df(closes))
    cross_idx = _first_crossover_index(df, "up")

    signal = generate_signal(df.iloc[: cross_idx + 1], has_open_position=False)
    assert signal.action == "BUY"
    assert signal.stop_price < signal.price < signal.target_price


def test_sell_on_downward_crossover_when_holding():
    rally = [100 + i * 1.5 for i in range(60)]
    drop = [rally[-1] - i * 2.5 for i in range(1, 30)]
    df = add_indicators(_make_df(rally + drop))
    cross_idx = _first_crossover_index(df, "down")

    signal = generate_signal(df.iloc[: cross_idx + 1], has_open_position=True)
    assert signal.action == "SELL"


def test_position_size_respects_risk_and_cap():
    qty = position_size(equity=10_000, entry_price=100, stop_price=95)
    # risk 1% of 10,000 = 100; stop distance = 5 -> 20 shares by risk
    assert qty == 20


def test_position_size_zero_when_stop_above_entry():
    assert position_size(equity=10_000, entry_price=100, stop_price=105) == 0
