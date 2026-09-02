"""Screener end-to-end: applica la pipeline a 4 stadi di STRATEGY.md
(Step 1: screening -> qualificazione trend -> pattern; Step 2: analisi
settoriale; Step 3-4: indicatori di conferma -> livelli -> money
management) su una lista di ticker, per entrambe le direzioni (long/short).

Sostituisce lo screener "Barchart"/"ProScreener" preconfigurato del corso
(non replicabile) con una scansione diretta via yfinance su una watchlist
esplicita (config.SHORT_TERM_WATCHLIST)."""
import logging
from dataclasses import dataclass, field

import pandas as pd

from common import config
from common.data import get_daily_bars, get_weekly_bars
from short_term import money_management, risk_checks, sector
from short_term.indicators import ema_ribbon, ribbon_alignment
from short_term.levels import EntryLevels, levels_for_setup_bar
from short_term.patterns import PatternMatch, detect_all
from short_term.trend import TrendQualification, qualify_trend

log = logging.getLogger("bot")


@dataclass
class Candidate:
    symbol: str
    direction: str
    pattern: str
    trend: TrendQualification
    levels: EntryLevels
    qty: int
    ribbon_aligned: bool
    sector_etf: str | None
    sector_passes: bool
    earnings_warn: bool
    sr_too_close: bool
    price_blocks_trade: bool
    has_divergence: bool
    notes: list[str] = field(default_factory=list)

    @property
    def is_actionable(self) -> bool:
        return self.qty > 0 and not self.price_blocks_trade


def scan_symbol(
    symbol: str,
    capital: float,
    open_positions_count: int,
    sp500_df: pd.DataFrame,
    russell_df: pd.DataFrame,
) -> list[Candidate]:
    daily = get_daily_bars(symbol, period="1y")
    weekly = get_weekly_bars(symbol, period="6y")

    if not money_management.can_open_new_position(open_positions_count):
        return []

    candidates: list[Candidate] = []
    ribbon = ema_ribbon(daily["close"])
    ribbon_state = ribbon_alignment(ribbon.iloc[-1], price=float(daily["close"].iloc[-1]))

    for direction in ("long", "short"):
        trend = qualify_trend(daily, direction)
        if not trend.qualifies:
            continue

        matches = detect_all(daily, direction)
        for match in matches:
            candidate = _build_candidate(
                symbol, direction, match, trend, daily, weekly, capital, ribbon_state, sp500_df, russell_df
            )
            if candidate is not None:
                candidates.append(candidate)

    return candidates


def _build_candidate(
    symbol: str,
    direction: str,
    match: PatternMatch,
    trend: TrendQualification,
    daily: pd.DataFrame,
    weekly: pd.DataFrame,
    capital: float,
    ribbon_state: str,
    sp500_df: pd.DataFrame,
    russell_df: pd.DataFrame,
) -> Candidate | None:
    levels = levels_for_setup_bar(daily, match.setup_bar_index, direction)
    if levels.risk_per_share <= 0:
        return None

    notes: list[str] = []

    ribbon_expected = "bullish" if direction == "long" else "bearish"
    ribbon_aligned = ribbon_state == ribbon_expected
    if not ribbon_aligned:
        notes.append(f"fascio EMA non allineato ({ribbon_state}), trend meno pulito")

    sector_etf = sector.get_sector_etf(symbol)
    sector_passes = False
    if sector_etf is not None:
        try:
            sector_df = get_daily_bars(sector_etf, period="1y")
            analysis = sector.sector_check(daily, sector_df, sp500_df, russell_df, direction, sector_etf)
            sector_passes = analysis.passes
            if not sector_passes:
                notes.append("analisi settoriale non conferma")
        except Exception as exc:
            log.warning("Sector check failed for %s (%s): %s", symbol, sector_etf, exc)
    else:
        notes.append("settore non determinato, analisi settoriale saltata")

    if match.pattern == "Bowai" and not sector_passes:
        # Quasi obbligatoria per il Bowai (STRATEGY.md 2.3)
        return None

    earnings = risk_checks.earnings_check(symbol)
    if earnings.warn:
        notes.append(f"earnings tra {earnings.days_until} giorni")

    sr = risk_checks.support_resistance_check(weekly, levels.entry, levels.risk_per_share, direction)
    if sr.too_close:
        notes.append(f"livello S/R a soli {sr.r_multiple_distance:.1f}R dall'entrata")

    price_check = risk_checks.price_level_check(levels.entry, direction)
    if price_check.blocks_trade:
        notes.append(f"prezzo {levels.entry:.2f} sotto la soglia minima per gli short")

    divergence = risk_checks.divergence_check(weekly, direction)
    if divergence.has_divergence:
        notes.append("divergenza prezzo/MACD settimanale contraria")

    qty = money_management.position_size(
        capital, config.SHORT_TERM_RISK_PER_TRADE_PCT, levels.risk_per_share, config.SHORT_TERM_FX_RATE
    )

    return Candidate(
        symbol=symbol,
        direction=direction,
        pattern=match.pattern,
        trend=trend,
        levels=levels,
        qty=qty,
        ribbon_aligned=ribbon_aligned,
        sector_etf=sector_etf,
        sector_passes=sector_passes,
        earnings_warn=earnings.warn,
        sr_too_close=sr.too_close,
        price_blocks_trade=price_check.blocks_trade,
        has_divergence=divergence.has_divergence,
        notes=notes,
    )


def build_full_market_universe(broker) -> list[str]:
    """Universo "tutto il mercato USA" (STRATEGY.md, richiesto per non
    limitarsi ai soliti titoli famosi): parte da tutti i titoli tradable su
    Alpaca, poi applica due prefiltri prima della pipeline completa (mima lo
    "Step 1: screening" del corso, necessario perché far girare la pipeline
    completa trend+pattern+settore su migliaia di titoli ogni giorno
    sarebbe troppo lento e colpirebbe i rate-limit di yfinance/Alpaca):
      1. liquidità (prezzo minimo, volume$ medio minimo)
      2. volatilità storica minima -- il backtest (STRATEGY.md "v4") ha
         mostrato che il solo filtro di liquidità lascia passare titoli
         difensivi a bassa volatilità (utility, beni di consumo) su cui un
         sistema trend-following rende storicamente peggio; senza questo
         filtro un universo allargato ha dato risultati PEGGIORI (CAGR
         quasi dimezzato, drawdown quasi raddoppiato) della watchlist
         curata, non migliori
    Tiene solo i migliori SHORT_TERM_FULL_MARKET_MAX_SYMBOLS per volume$
    tra i sopravvissuti a entrambi i filtri."""
    all_symbols = broker.list_tradable_symbols()
    log.info("Full-market: %d titoli tradable su Alpaca (NYSE/NASDAQ/ARCA/AMEX/BATS).", len(all_symbols))

    liquidity = broker.liquidity_snapshot(all_symbols)
    liquid = [
        s
        for s, data in liquidity.items()
        if data["price"] >= config.SHORT_TERM_MIN_PRICE_FULL_MARKET
        and data["dollar_volume"] >= config.SHORT_TERM_MIN_DOLLAR_VOLUME
    ]
    liquid.sort(key=lambda s: liquidity[s]["dollar_volume"], reverse=True)
    log.info(
        "Full-market: %d titoli dopo il prefiltro di liquidità (prezzo>=%.0f, volume$>=%.0f).",
        len(liquid), config.SHORT_TERM_MIN_PRICE_FULL_MARKET, config.SHORT_TERM_MIN_DOLLAR_VOLUME,
    )

    # Il filtro di volatilità richiede una chiamata dati aggiuntiva per
    # titolo: applicato solo a un pool 3x più ampio del tetto finale (non a
    # tutti i sopravvissuti alla liquidità, potenzialmente migliaia), per
    # tenere sotto controllo i tempi anche sull'universo full-market.
    pool = liquid[: config.SHORT_TERM_FULL_MARKET_MAX_SYMBOLS * 3]
    volatility = broker.volatility_snapshot(pool)
    min_vol = config.SHORT_TERM_MIN_ANNUALIZED_VOLATILITY_PCT / 100
    survivors = [s for s in pool if volatility.get(s, 0.0) >= min_vol]
    survivors.sort(key=lambda s: liquidity[s]["dollar_volume"], reverse=True)

    top = survivors[: config.SHORT_TERM_FULL_MARKET_MAX_SYMBOLS]
    log.info(
        "Full-market: %d titoli dopo il prefiltro di volatilità (>=%.0f%% annualizzata su un pool di %d), "
        "tenuti i migliori %d per volume$.",
        len(survivors), config.SHORT_TERM_MIN_ANNUALIZED_VOLATILITY_PCT, len(pool), len(top),
    )
    return top


def screen_universe(
    symbols: list[str] | None = None,
    capital: float | None = None,
    open_positions_count: int = 0,
    broker=None,
) -> list[Candidate]:
    if symbols is None:
        if config.SHORT_TERM_USE_FULL_MARKET:
            from common.broker import Broker

            symbols = build_full_market_universe(broker or Broker())
        else:
            symbols = config.SHORT_TERM_WATCHLIST
    capital = capital if capital is not None else config.SHORT_TERM_CAPITAL

    sp500_df = get_daily_bars(sector.SP500_PROXY, period="1y")
    russell_df = get_daily_bars(sector.RUSSELL2000_PROXY, period="1y")

    all_candidates: list[Candidate] = []
    for symbol in symbols:
        try:
            all_candidates.extend(scan_symbol(symbol, capital, open_positions_count, sp500_df, russell_df))
        except Exception:
            log.exception("Error screening %s", symbol)
    return all_candidates
