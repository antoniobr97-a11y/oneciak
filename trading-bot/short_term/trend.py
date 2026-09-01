"""Qualificazione del trend: 6 parametri, ne bastano 2-3 su 6 (raro
trovarli tutti). Vedi STRATEGY.md 2.1. Finestra tipica: ultimi 2-3 mesi."""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from common import config
from short_term.indicators import adx

# Non tutte le soglie sono numeri espliciti nel corso (es. "gap" e "barre ad
# ampio range" non hanno una soglia % dichiarata) -- dove manca un numero
# preciso si usa una soglia ragionevole e configurabile, segnalata qui.
GAP_THRESHOLD_PCT = 1.0  # assunzione: gap = open oltre l'1% dalla chiusura precedente
WIDE_RANGE_PERCENTILE = 75  # assunzione: "ampio range" = range nel quartile superiore del periodo
WIDE_RANGE_MIN_COUNT = 2
PERSISTENCE_TOLERANCE_ATR_MULT = 1.0


@dataclass
class TrendQualification:
    direction: str
    score: int
    satisfied: dict[str, bool] = field(default_factory=dict)

    @property
    def qualifies(self) -> bool:
        return self.score >= config.TREND_MIN_QUALIFIERS


def _window(df: pd.DataFrame, lookback: int) -> pd.DataFrame:
    return df.iloc[-lookback:] if len(df) > lookback else df


def performance_qualifier(df: pd.DataFrame, direction: str, lookback: int) -> bool:
    w = _window(df, lookback)
    if len(w) < 2:
        return False
    if direction == "long":
        low_idx = w["low"].idxmin()
        after_low = w.loc[low_idx:]
        move_pct = (after_low["high"].max() / w["low"].min() - 1) * 100
    else:
        high_idx = w["high"].idxmax()
        after_high = w.loc[high_idx:]
        move_pct = (after_high["low"].min() / w["high"].max() - 1) * 100
    threshold = config.TREND_PERFORMANCE_THRESHOLD_PCT
    return move_pct >= threshold if direction == "long" else move_pct <= -threshold


def gap_qualifier(df: pd.DataFrame, direction: str, lookback: int) -> bool:
    w = _window(df, lookback)
    prev_close = w["close"].shift(1)
    gap_pct = (w["open"] - prev_close) / prev_close * 100
    if direction == "long":
        return bool((gap_pct >= GAP_THRESHOLD_PCT).any())
    return bool((gap_pct <= -GAP_THRESHOLD_PCT).any())


def wide_range_qualifier(df: pd.DataFrame, direction: str, lookback: int) -> bool:
    w = _window(df, lookback)
    if len(w) < 10:
        return False
    bar_range = w["high"] - w["low"]
    threshold = np.percentile(bar_range.dropna(), WIDE_RANGE_PERCENTILE)
    is_wide = bar_range >= threshold

    close_position = (w["close"] - w["low"]) / bar_range.replace(0, np.nan)  # 0=low, 1=high
    if direction == "long":
        extreme_close = close_position >= 0.75
    else:
        extreme_close = close_position <= 0.25

    matches = is_wide & extreme_close
    return int(matches.sum()) >= WIDE_RANGE_MIN_COUNT


def _swing_points(series: pd.Series, order: int = 3) -> list[tuple[int, float]]:
    """Fractal semplice: un punto è uno swing high/low se è l'estremo tra
    `order` barre prima e dopo."""
    points = []
    values = series.to_numpy()
    for i in range(order, len(values) - order):
        window = values[i - order: i + order + 1]
        if values[i] == window.max() or values[i] == window.min():
            points.append((i, values[i]))
    return points


def harmony_qualifier(df: pd.DataFrame, direction: str, lookback: int) -> bool:
    w = _window(df, lookback)
    if len(w) < 10:
        return False
    highs = _swing_points(w["high"], order=2)
    lows = _swing_points(w["low"], order=2)
    if len(highs) < 2 or len(lows) < 2:
        return False

    high_vals = [v for _, v in highs][-4:]
    low_vals = [v for _, v in lows][-4:]

    if direction == "long":
        highs_rising = sum(1 for a, b in zip(high_vals, high_vals[1:]) if b > a)
        lows_rising = sum(1 for a, b in zip(low_vals, low_vals[1:]) if b > a)
        return highs_rising >= len(high_vals) // 2 and lows_rising >= len(low_vals) // 2
    highs_falling = sum(1 for a, b in zip(high_vals, high_vals[1:]) if b < a)
    lows_falling = sum(1 for a, b in zip(low_vals, low_vals[1:]) if b < a)
    return highs_falling >= len(high_vals) // 2 and lows_falling >= len(low_vals) // 2


def adx_qualifier(df: pd.DataFrame, period: int = 14) -> bool:
    adx_series = adx(df["high"], df["low"], df["close"], period)
    if adx_series.isna().iloc[-1]:
        return False
    last = adx_series.iloc[-1]
    if last > config.TREND_ADX_THRESHOLD:
        return True
    lookback_bars = min(10, len(adx_series) - 1)
    if lookback_bars <= 0 or adx_series.isna().iloc[-1 - lookback_bars]:
        return False
    return bool(last > adx_series.iloc[-1 - lookback_bars])


def persistence_qualifier(df: pd.DataFrame, window: int | None = None) -> bool:
    """Una retta di tendenza (regressione lineare sulle chiusure) intercetta
    la maggior parte delle ultime N barre, entro una tolleranza."""
    window = window or config.TREND_PERSISTENCE_WINDOW
    w = _window(df, window)
    if len(w) < window:
        return False

    closes = w["close"].to_numpy()
    x = np.arange(len(closes))
    slope, intercept = np.polyfit(x, closes, 1)
    fitted = slope * x + intercept

    atr_val = (w["high"] - w["low"]).mean()
    tolerance = atr_val * PERSISTENCE_TOLERANCE_ATR_MULT
    touches = np.abs(closes - fitted) <= tolerance
    return bool(touches.sum() >= len(closes) * 0.6)


def qualify_trend(df: pd.DataFrame, direction: str, lookback: int | None = None) -> TrendQualification:
    lookback = lookback or config.TREND_LOOKBACK_DAYS
    checks = {
        "performance": performance_qualifier(df, direction, lookback),
        "gap": gap_qualifier(df, direction, lookback),
        "wide_range": wide_range_qualifier(df, direction, lookback),
        "harmony": harmony_qualifier(df, direction, lookback),
        "adx": adx_qualifier(df),
        "persistence": persistence_qualifier(df),
    }
    return TrendQualification(direction=direction, score=sum(checks.values()), satisfied=checks)
