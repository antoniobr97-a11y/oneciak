"""Analisi settoriale (Step 2, STRATEGY.md 2.3). Non obbligatoria (tranne
per il Bowai), riduce il rischio di operare contro il gruppo del titolo.

I sotto-indici "Dow Jones US ..." citati nel corso non sono liberamente
disponibili: qui si usano gli ETF settoriali SPDR come proxy (vedi
STRATEGY.md, sezione finale)."""
import logging
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from common import config
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


def get_sector_etf(symbol: str) -> str | None:
    """Best-effort: legge il settore GICS da yfinance e lo mappa sull'ETF
    SPDR corrispondente. Ritorna None se il settore non è disponibile o non
    è mappato (nessun dato fittizio)."""
    try:
        info = yf.Ticker(symbol).info
        sector = info.get("sector")
    except Exception as exc:
        log.warning("Could not fetch sector info for %s: %s", symbol, exc)
        return None
    return SPDR_SECTOR_ETFS.get(sector)


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
