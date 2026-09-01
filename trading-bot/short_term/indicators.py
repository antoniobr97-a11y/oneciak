"""Plain pandas/numpy technical indicators used by the short-term strategy
(no TA-Lib dependency). See STRATEGY.md 2.1 and 2.6."""
import numpy as np
import pandas as pd

EMA_SHORT_PERIODS = [3, 5, 8, 10, 12, 15]
EMA_LONG_PERIODS = [30, 35, 40, 45, 50, 60]


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, min_periods=period, adjust=False).mean()


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def avg_daily_range(high: pd.Series, low: pd.Series, period: int = 10) -> pd.Series:
    """'Indicatore di Volatilità' di STRATEGY.md 2.4: media mobile
    dell'escursione (max-min) delle ultime N barre -- distinto dalla
    Historical Volatility (che è basata sui log-return)."""
    return (high - low).rolling(window=period, min_periods=period).mean()


def historical_volatility(close: pd.Series, period: int = 20) -> pd.Series:
    """Deviazione standard annualizzata dei log-return, in %."""
    log_returns = np.log(close / close.shift(1))
    return log_returns.rolling(window=period, min_periods=period).std() * np.sqrt(252) * 100


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index)

    tr = pd.concat(
        [high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)

    atr_smooth = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr_smooth
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr_smooth

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = macd_line.ewm(span=signal, min_periods=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})


def ema_ribbon(close: pd.Series) -> pd.DataFrame:
    """Fascio di EMA multiple (STRATEGY.md 2.6): brevi 3/5/8/10/12/15,
    lunghe 30/35/40/45/50/60."""
    cols = {f"ema_{p}": ema(close, p) for p in EMA_SHORT_PERIODS + EMA_LONG_PERIODS}
    return pd.DataFrame(cols)


def ribbon_alignment(ribbon_row: pd.Series) -> str:
    """'bullish' se tutte le EMA brevi sono sopra tutte le lunghe, 'bearish'
    se sotto, 'mixed' (intrecciate) altrimenti -- trend non pulito."""
    shorts = [ribbon_row[f"ema_{p}"] for p in EMA_SHORT_PERIODS]
    longs = [ribbon_row[f"ema_{p}"] for p in EMA_LONG_PERIODS]
    if any(pd.isna(v) for v in shorts + longs):
        return "mixed"
    if min(shorts) > max(longs):
        return "bullish"
    if max(shorts) < min(longs):
        return "bearish"
    return "mixed"
