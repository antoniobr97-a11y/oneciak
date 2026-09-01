"""Recent daily bars pulled from Alpaca's market data API (used for live /
paper trading decisions, as opposed to data.py's yfinance bars which are
used for backtesting)."""
from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from common import config


def get_recent_daily_bars(symbol: str, lookback_days: int = 400) -> pd.DataFrame:
    client = StockHistoricalDataClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY)
    start = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    request = StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day, start=start)
    bars = client.get_stock_bars(request).df

    if bars.empty:
        raise ValueError(f"No data returned for {symbol}")

    if isinstance(bars.index, pd.MultiIndex):
        bars = bars.xs(symbol, level="symbol")

    df = bars[["open", "high", "low", "close", "volume"]]
    df.index.name = "date"
    return df
