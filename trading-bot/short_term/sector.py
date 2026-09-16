"""Analisi settoriale (Step 2, STRATEGY.md 2.3). Non obbligatoria (tranne
per il Bowai), riduce il rischio di operare contro il gruppo del titolo.

I sotto-indici "Dow Jones US ..." citati nel corso non sono liberamente
disponibili: qui si usano gli ETF settoriali SPDR come proxy (vedi
STRATEGY.md, sezione finale)."""
import logging
from dataclasses import dataclass
from datetime import date

import pandas as pd
import yfinance as yf

from common import config, symbol_cache
from common.market_time import market_today
from short_term.indicators import historical_volatility

log = logging.getLogger("bot")

SPDR_SECTOR_ETFS = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Financials": "XLF",
    "Energy": "XLE",
    "Healthcare": "XLV",
    "Health Care": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Discretionary": "XLY",
    "Consumer Defensive": "XLP",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB",
    "Materials": "XLB",
    "Communication Services": "XLC",
}

SP500_PROXY = "SPY"
RUSSELL2000_PROXY = "IWM"


def get_sector_etf(symbol: str, today: date | None = None) -> str | None:
    """Best-effort: legge il settore GICS da yfinance e lo mappa sull'ETF
    SPDR corrispondente. Ritorna None se il settore non è disponibile o non
    è mappato (nessun dato fittizio).

    Il risultato viene messo in cache su disco (common/symbol_cache.py). Non
    e' solo velocita': `yf.Ticker(symbol).info` e' la chiamata piu' lenta e
    piu' limitata da Yahoo dell'intera scansione, e quando veniva rifiutata
    per rate-limit questa funzione restituiva None -- cioe' il candidato
    perdeva la conferma settoriale per un motivo che non ha niente a che
    fare con il suo settore. Con la cache la risposta e' la stessa fra un
    ciclo e l'altro, quindi l'analisi e' ripetibile."""
    today = today or market_today()
    cached = symbol_cache.get(symbol, "sector_etf", today, symbol_cache.SECTOR_TTL_DAYS)
    if cached is not symbol_cache.MISSING:
        return cached
    etf, _, _ = _scarica_e_memorizza(symbol, today)
    return etf


def _scarica_e_memorizza(symbol: str, today: date) -> tuple[str | None, str | None, bool]:
    """Una sola chiamata di rete che riempie ENTRAMBE le voci di cache
    (settore e tipo di strumento). Ritorna (etf, tipo, riuscito).

    Sta in una funzione sua perche' get_sector_etf esce subito se il
    settore e' gia' in cache: chiamarlo per popolare il tipo di strumento
    non funzionava, ed e' il bug che ha fatto passare l'ETF EWT il
    2026-09-16 nonostante SHORT_TERM_STOCKS_ONLY fosse acceso."""
    try:
        info = yf.Ticker(symbol).info
        sector = info.get("sector")
        quote_type = info.get("quoteType")
    except Exception as exc:
        # Non si mette in cache un fallimento di rete: sarebbe come
        # decidere per 30 giorni che questo titolo non ha settore.
        log.warning("Could not fetch sector info for %s: %s", symbol, exc)
        return None, None, False

    etf = SPDR_SECTOR_ETFS.get(sector)
    symbol_cache.put(symbol, "sector_etf", etf, today)
    # Stessa risposta di rete, nessuna chiamata in piu': si registra anche
    # che tipo di strumento e', per poter tenere fuori gli ETF dal lato
    # azionario (vedi is_equity).
    symbol_cache.put(symbol, "quote_type", quote_type, today)
    return etf, quote_type, True


def is_equity(symbol: str, today: date | None = None) -> bool | None:
    """True se lo strumento e' un'AZIONE, False se e' un ETF o altro, None
    se non si sa.

    Serve a tenere il lato di breve termine su quello che il corso insegna:
    titoli azionari. Un ETF (esempio visto dal vivo: IBIT, che replica il
    bitcoin) non ha settore, quindi salterebbe l'analisi settoriale -- che
    il corso chiama "veramente fondamentale" -- e passerebbe comunque.

    La distinzione NON e' "ha un settore": un'azione vera puo' non averlo
    per un buco nei dati di Yahoo, e scartarla per quello sarebbe un
    errore diverso. Si guarda il tipo di strumento dichiarato.

    Il dato arriva dalla stessa risposta di rete gia' usata per il settore
    ed e' nella stessa cache: nessuna chiamata aggiuntiva."""
    today = today or market_today()
    cached = symbol_cache.get(symbol, "quote_type", today, symbol_cache.SECTOR_TTL_DAYS)
    if cached is symbol_cache.MISSING:
        # Si scarica DIRETTAMENTE, senza passare da get_sector_etf: quello
        # esce subito quando il settore e' gia' in cache (com'e' per ogni
        # titolo gia' visto in un ciclo precedente) e lascerebbe il tipo di
        # strumento vuoto per sempre.
        _, quote_type, riuscito = _scarica_e_memorizza(symbol, today)
        if not riuscito:
            return None
        cached = quote_type
    if cached is None:
        return None
    return str(cached).upper() == "EQUITY"


def relative_strength(price_a: pd.Series, price_b: pd.Series) -> pd.Series:
    aligned_a, aligned_b = price_a.align(price_b, join="inner")
    return aligned_a / aligned_b


def is_rising(series: pd.Series, lookback: int) -> bool:
    w = series.iloc[-lookback:] if len(series) > lookback else series
    w = w.dropna()
    return bool(len(w) >= 2 and w.iloc[-1] > w.iloc[0])


def is_falling(series: pd.Series, lookback: int) -> bool:
    w = series.iloc[-lookback:] if len(series) > lookback else series
    w = w.dropna()
    return bool(len(w) >= 2 and w.iloc[-1] < w.iloc[0])


@dataclass
class SectorAnalysis:
    sector_etf: str | None
    same_direction: bool
    rs_stock_vs_sector_ok: bool
    rs_sector_vs_sp500_ok: bool
    rs_sector_vs_russell_ok: bool
    hv_ordering_ok: bool

    @property
    def passes(self) -> bool:
        if self.sector_etf is None:
            return False
        return (
            self.same_direction
            and self.rs_stock_vs_sector_ok
            and self.rs_sector_vs_sp500_ok
            and self.rs_sector_vs_russell_ok
        )


def sector_check(
    stock_df: pd.DataFrame,
    sector_df: pd.DataFrame,
    sp500_df: pd.DataFrame,
    russell_df: pd.DataFrame,
    direction: str,
    sector_etf: str | None = None,
    lookback: int | None = None,
) -> SectorAnalysis:
    lookback = lookback or config.SECTOR_RS_LOOKBACK_DAYS
    trend_check = is_rising if direction == "long" else is_falling

    sector_close = sector_df["close"]
    stock_close = stock_df["close"]

    sector_direction_ok = trend_check(sector_close, lookback)

    rs_stock_sector = relative_strength(stock_close, sector_close)
    rs_stock_vs_sector_ok = trend_check(rs_stock_sector, lookback)

    rs_sector_sp500 = relative_strength(sector_close, sp500_df["close"])
    rs_sector_vs_sp500_ok = trend_check(rs_sector_sp500, lookback)

    rs_sector_russell = relative_strength(sector_close, russell_df["close"])
    rs_sector_vs_russell_ok = trend_check(rs_sector_russell, lookback)

    hv_stock = historical_volatility(stock_close).iloc[-1]
    hv_sector = historical_volatility(sector_close).iloc[-1]
    hv_market = historical_volatility(sp500_df["close"]).iloc[-1]
    hv_ordering_ok = bool(
        pd.notna(hv_stock) and pd.notna(hv_sector) and pd.notna(hv_market) and hv_stock > hv_sector > hv_market
    )

    return SectorAnalysis(
        sector_etf=sector_etf,
        same_direction=sector_direction_ok,
        rs_stock_vs_sector_ok=rs_stock_vs_sector_ok,
        rs_sector_vs_sp500_ok=rs_sector_vs_sp500_ok,
        rs_sector_vs_russell_ok=rs_sector_vs_russell_ok,
        hv_ordering_ok=hv_ordering_ok,
    )
