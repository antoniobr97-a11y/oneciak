"""Historical bars via yfinance (free, no API key -- used for backtests, for
the long-term monthly signal, and to warm up short-term indicators before a
live/paper cycle)."""
import pandas as pd
import yfinance as yf

_OHLCV = ["open", "high", "low", "close", "volume"]


def get_daily_bars(symbol: str, period: str = "2y") -> pd.DataFrame:
    """Returns a DataFrame indexed by date with columns: open, high, low,
    close, volume."""
    raw = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=True)
    if raw.empty:
        raise ValueError(f"No data returned for {symbol}")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw.rename(
        columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    )[_OHLCV]
    df.index.name = "date"
    return df


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample daily bars to a coarser timeframe. rule: 'W' (weekly, ending
    Friday) or 'ME' (monthly, calendar month end)."""
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    out = df.resample(rule).agg(agg).dropna(how="all")
    return out


def closed_weekly_bars(daily: pd.DataFrame) -> pd.DataFrame:
    """Barre settimanali, esclusa la settimana IN CORSO.

    Il resample include sempre la settimana corrente parziale come ultima
    riga. I controlli che la usano (supporti/resistenze e divergenza
    prezzo/MACD, short_term/risk_checks.py) leggono i punti di inversione
    piu' recenti: un massimo settimanale ancora in formazione ne crea uno
    che a fine settimana potrebbe non esistere.

    Il backtest storico scarta gia' la settimana in corso, il codice live
    no: e' la stessa incoerenza barra-incompleta trovata prima sul segnale
    mensile Advanced e sulle barre giornaliere (vedi STRATEGY.md). Regola
    identica al backtest: la settimana e' chiusa solo se l'ultima barra
    giornaliera e' un venerdi'."""
    weekly = resample(daily, "W")
    if len(daily) and len(weekly) and daily.index[-1].dayofweek != 4:
        weekly = weekly.iloc[:-1]
    return weekly


def get_weekly_bars(symbol: str, period: str = "3y") -> pd.DataFrame:
    return closed_weekly_bars(get_daily_bars(symbol, period=period))


def get_monthly_bars(symbol: str, period: str = "10y") -> pd.DataFrame:
    return resample(get_daily_bars(symbol, period=period), "ME")
