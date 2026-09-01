"""Historical daily bars via yfinance (free, no API key -> used for backtests
and for warming up indicators before a live/paper trading cycle)."""
import pandas as pd
import yfinance as yf


def get_daily_bars(symbol: str, period: str = "2y") -> pd.DataFrame:
    """Returns a DataFrame indexed by date with columns:
    open, high, low, close, volume."""
    raw = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=True)
    if raw.empty:
        raise ValueError(f"No data returned for {symbol}")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )[["open", "high", "low", "close", "volume"]]
    df.index.name = "date"
    return df
