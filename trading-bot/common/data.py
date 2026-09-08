"""Historical bars via yfinance (free, no API key -- used for backtests, for
the long-term monthly signal, and to warm up short-term indicators before a
live/paper cycle)."""
import logging

import pandas as pd
import yfinance as yf

log = logging.getLogger("bot")

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


def get_daily_bars_batch(symbols: list[str], period: str = "2y", chunk_size: int = 50) -> dict[str, pd.DataFrame]:
    """Barre giornaliere per PIU' titoli in una sola chiamata per lotto.

    E' la differenza fra "il bot guarda i 300 titoli piu' scambiati" e "il
    bot guarda tutto il mercato". Con `get_daily_bars` la scansione fa un
    download HTTP per titolo, uno dopo l'altro: e' quello -- non la CPU, non
    la logica dei pattern -- a fissare il tetto di quanti titoli si possono
    analizzare in una sera. yfinance accetta una lista e scarica il lotto in
    parallelo, quindi lo stesso tempo copre un universo molto piu' ampio.

    I lotti sono piccoli di proposito: un lotto che fallisce fa perdere solo
    quei titoli (ripescati poi uno per uno da chi chiama), non l'intera
    scansione, e URL troppo lunghe vengono rifiutate da Yahoo.

    Ritorna solo i titoli per cui sono arrivati dati: un simbolo assente dal
    risultato NON e' un titolo senza setup, e chi chiama deve trattarlo come
    tale (vedi screener.screen_universe)."""
    out: dict[str, pd.DataFrame] = {}
    unique = list(dict.fromkeys(symbols))
    for i in range(0, len(unique), chunk_size):
        chunk = unique[i : i + chunk_size]
        try:
            raw = yf.download(
                chunk, period=period, interval="1d", progress=False,
                auto_adjust=True, group_by="ticker", threads=True,
            )
        except Exception as exc:
            log.warning("Scaricamento a lotti fallito per il lotto che inizia con %s: %s", chunk[0], exc)
            continue
        if raw is None or raw.empty:
            continue
        for symbol in chunk:
            frame = _extract_symbol(raw, symbol, single=len(chunk) == 1)
            if frame is not None:
                out[symbol] = frame
    return out


def _extract_symbol(raw: pd.DataFrame, symbol: str, single: bool) -> pd.DataFrame | None:
    """Estrae il DataFrame di un titolo dal risultato di un download a
    lotti, nella stessa forma che restituisce get_daily_bars.

    La forma del risultato di yfinance non e' una sola: con piu' titoli le
    colonne sono a due livelli, di solito (titolo, campo) con
    group_by="ticker" ma (campo, titolo) in altre configurazioni, e con un
    solo titolo possono essere piatte. Si provano tutte invece di
    scommettere su una: sbagliare qui non da' un errore, fa sparire in
    silenzio i titoli di quel lotto."""
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            if symbol in raw.columns.get_level_values(0):
                frame = raw[symbol]
            elif symbol in raw.columns.get_level_values(1):
                frame = raw.xs(symbol, axis=1, level=1)
            else:
                return None
        elif single:
            frame = raw
        else:
            return None
        frame = frame.rename(
            columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
        )
        if not set(_OHLCV).issubset(frame.columns):
            return None
        # Un titolo assente dal lotto torna comunque come colonne di NaN:
        # va scartato, non passato alla pipeline come "grafico piatto".
        frame = frame[_OHLCV].dropna(how="all")
        if frame.empty:
            return None
        frame.index.name = "date"
        return frame
    except Exception as exc:
        log.warning("Dati illeggibili per %s nel download a lotti: %s", symbol, exc)
        return None


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


def get_weekly_bars_batch(symbols: list[str], period: str = "6y", chunk_size: int = 50) -> dict[str, pd.DataFrame]:
    """Come get_daily_bars_batch, ma settimanali: stesso risparmio di
    chiamate per i titoli il cui trend ha qualificato (gli unici per cui i
    settimanali servono, vedi screener.scan_symbol)."""
    return {
        symbol: closed_weekly_bars(daily)
        for symbol, daily in get_daily_bars_batch(symbols, period=period, chunk_size=chunk_size).items()
    }


def get_monthly_bars(symbol: str, period: str = "10y") -> pd.DataFrame:
    return resample(get_daily_bars(symbol, period=period), "ME")
