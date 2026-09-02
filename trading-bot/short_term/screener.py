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
from short_term.indicators import ema_ribbon, ribbon_alignment, sma
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

    # Vicinanza al massimo/minimo a 52 settimane (0-1, 1 = sul massimo per
    # un long / sul minimo per uno short). Usata per dare la precedenza ai
    # candidati migliori quando sono piu' dei posti disponibili nel tetto di
    # rischio aggregato -- vedi rank_candidates.
    proximity_52w: float = 0.0

    @property
    def is_actionable(self) -> bool:
        return self.qty > 0 and not self.price_blocks_trade


ALL_DIRECTIONS = ("long", "short")
TRADING_DAYS_52W = 252


def proximity_to_52w_extreme(daily: pd.DataFrame, direction: str) -> float:
    """Quanto il titolo e' vicino al suo estremo a 52 settimane: per un long
    prezzo/massimo (1.0 = nuovo massimo annuale), per uno short minimo/prezzo
    (1.0 = nuovo minimo annuale). 0.0 se i dati non bastano.

    George & Hwang (2004), "The 52-Week High and Momentum Investing": la
    vicinanza al massimo annuale predice i rendimenti futuri meglio del
    momentum classico. Il corso (video 47) dice la stessa cosa in altre
    parole: "concentrarsi sulle migliori opportunita', non riempire uno
    slot con un setup mediocre"."""
    closes = daily["close"].dropna()
    if len(closes) < 2:
        return 0.0
    window = closes.iloc[-TRADING_DAYS_52W:]
    last = float(window.iloc[-1])
    if direction == "long":
        high = float(window.max())
        return last / high if high > 0 else 0.0
    low = float(window.min())
    return low / last if last > 0 else 0.0


# Gli ETF settoriali sono ~11 in tutto e servono a ogni candidato: senza
# cache, con l'universo full-market (fino a 300 titoli) verrebbero
# riscaricati centinaia di volte per ciclo. La cache dura un ciclo e viene
# svuotata all'inizio di ogni scansione (i dati devono essere freschi).
_sector_cache: dict[str, pd.DataFrame] = {}


def _sector_bars(sector_etf: str) -> pd.DataFrame:
    if sector_etf not in _sector_cache:
        _sector_cache[sector_etf] = get_daily_bars(sector_etf, period="1y")
    return _sector_cache[sector_etf]


def rank_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Ordina i candidati dal migliore al peggiore. Conta solo quando i
    candidati sono piu' dei posti liberi nel tetto di rischio aggregato:
    in quel caso il bot prende i primi, non i primi in ordine alfabetico.
    Validato nel backtest (STRATEGY.md "v9"): a parita' di numero di
    operazioni migliora il rendimento E riduce il drawdown."""
    return sorted(candidates, key=lambda c: c.proximity_52w, reverse=True)


def allowed_directions(sp500_df: pd.DataFrame) -> tuple[str, ...]:
    """Direzioni ammesse in questo ciclo:
      - SHORT_TERM_ALLOW_SHORTS=false (default, STRATEGY.md "v6"): mai short
      - filtro di regime di mercato (STRATEGY.md "v5"): long solo se
        l'indice chiude sopra la sua SMA di lungo periodo, short solo se
        sotto. Se il filtro e' disattivato o lo storico non basta per la
        media, il regime non blocca nulla (nessun blocco "per sicurezza"
        non motivato dai dati).
    Puo' essere vuota (regime ribassista + short disattivati): in quel caso
    il bot resta fuori dal mercato, che e' esattamente cio' che il
    backtest v6 fa negli anni orso."""
    base = ALL_DIRECTIONS if config.SHORT_TERM_ALLOW_SHORTS else ("long",)
    if not config.MARKET_REGIME_FILTER:
        return base
    closes = sp500_df["close"]
    if len(closes) < config.MARKET_REGIME_MA_PERIOD:
        return base
    long_ma = sma(closes, config.MARKET_REGIME_MA_PERIOD).iloc[-1]
    if pd.isna(long_ma):
        return base
    regime = ("long",) if float(closes.iloc[-1]) > float(long_ma) else ("short",)
    return tuple(d for d in base if d in regime)


def scan_symbol(
    symbol: str,
    capital: float,
    open_positions_count: int,
    sp500_df: pd.DataFrame,
    russell_df: pd.DataFrame,
    directions: tuple[str, ...] = ALL_DIRECTIONS,
) -> list[Candidate]:
    daily = get_daily_bars(symbol, period="1y")
    weekly = get_weekly_bars(symbol, period="6y")

    if not money_management.can_open_new_position(open_positions_count):
        return []

    candidates: list[Candidate] = []
    ribbon = ema_ribbon(daily["close"])
    ribbon_state = ribbon_alignment(ribbon.iloc[-1], price=float(daily["close"].iloc[-1]))

    for direction in directions:
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
    levels = levels_for_setup_bar(daily, match.setup_bar_index, direction, stop_bar_index=match.stop_bar_index)
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
            sector_df = _sector_bars(sector_etf)
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
        proximity_52w=proximity_to_52w_extreme(daily, direction),
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
        and data.get("volume", 0.0) >= config.SHORT_TERM_MIN_SHARE_VOLUME
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
    _sector_cache.clear()  # dati freschi a ogni ciclo

    sp500_df = get_daily_bars(sector.SP500_PROXY, period="2y")
    russell_df = get_daily_bars(sector.RUSSELL2000_PROXY, period="1y")

    directions = allowed_directions(sp500_df)
    if not directions:
        log.info("Nessuna direzione ammessa oggi (regime ribassista, short disattivati): nessuna nuova entrata.")
        return []
    if directions != ALL_DIRECTIONS:
        log.info("Direzioni ammesse oggi (regime %s vs SMA%d, short=%s): %s.",
                 sector.SP500_PROXY, config.MARKET_REGIME_MA_PERIOD, config.SHORT_TERM_ALLOW_SHORTS, ", ".join(d.upper() for d in directions))

    all_candidates: list[Candidate] = []
    for symbol in symbols:
        try:
            all_candidates.extend(
                scan_symbol(symbol, capital, open_positions_count, sp500_df, russell_df, directions=directions)
            )
        except Exception:
            log.exception("Error screening %s", symbol)
    # I candidati escono in ordine di scansione (alfabetico): quando sono
    # piu' dei posti liberi nel tetto di rischio, chi arriva prima nella
    # lista vince, che e' un criterio senza senso. Ordinati per vicinanza
    # all'estremo a 52 settimane (STRATEGY.md "v9").
    return rank_candidates(all_candidates)
