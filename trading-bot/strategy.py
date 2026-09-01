"""SMA-crossover + RSI-filtered strategy, with an ATR-based stop/target.

Signal logic (evaluated on the latest fully-closed daily bar):
  BUY  -> fast SMA crosses above slow SMA AND RSI is not overbought
  SELL -> fast SMA crosses below slow SMA (used to flatten an open long)
  HOLD -> anything else

This is intentionally simple and fully deterministic so it can be
backtested and reasoned about. It is a starting point, not investment
advice.
"""
from dataclasses import dataclass

import pandas as pd

import config
from indicators import atr, rsi, sma


@dataclass
class Signal:
    action: str  # "BUY", "SELL", "HOLD"
    price: float
    stop_price: float | None = None
    target_price: float | None = None
    reason: str = ""


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """df must have columns: open, high, low, close, volume (indexed by date)."""
    out = df.copy()
    out["sma_fast"] = sma(out["close"], config.SMA_FAST)
    out["sma_slow"] = sma(out["close"], config.SMA_SLOW)
    out["rsi"] = rsi(out["close"], config.RSI_PERIOD)
    out["atr"] = atr(out["high"], out["low"], out["close"], config.ATR_PERIOD)
    return out


def generate_signal(df: pd.DataFrame, has_open_position: bool) -> Signal:
    """df must already contain indicator columns (see add_indicators) and
    have at least SMA_SLOW + 1 rows of history."""
    if len(df) < config.SMA_SLOW + 2:
        return Signal("HOLD", float(df["close"].iloc[-1]), reason="not enough history")

    last = df.iloc[-1]
    prev = df.iloc[-2]

    if pd.isna(last["sma_slow"]) or pd.isna(prev["sma_slow"]) or pd.isna(last["atr"]):
        return Signal("HOLD", float(last["close"]), reason="indicators warming up")

    crossed_up = prev["sma_fast"] <= prev["sma_slow"] and last["sma_fast"] > last["sma_slow"]
    crossed_down = prev["sma_fast"] >= prev["sma_slow"] and last["sma_fast"] < last["sma_slow"]

    price = float(last["close"])
    atr_val = float(last["atr"])

    if not has_open_position:
        if crossed_up and last["rsi"] < config.RSI_OVERBOUGHT:
            stop = price - config.ATR_STOP_MULT * atr_val
            target = price + config.REWARD_RISK_RATIO * (price - stop)
            return Signal(
                "BUY",
                price,
                stop_price=round(stop, 2),
                target_price=round(target, 2),
                reason=f"SMA{config.SMA_FAST} crossed above SMA{config.SMA_SLOW}, RSI={last['rsi']:.1f}",
            )
        return Signal("HOLD", price, reason="no entry condition met")

    # Have an open position: look for an exit signal (the broker-side
    # stop-loss/take-profit bracket handles the risk-based exit; this is
    # the trend-following exit).
    if crossed_down:
        return Signal(
            "SELL",
            price,
            reason=f"SMA{config.SMA_FAST} crossed below SMA{config.SMA_SLOW}",
        )
    return Signal("HOLD", price, reason="holding position, no exit condition met")
