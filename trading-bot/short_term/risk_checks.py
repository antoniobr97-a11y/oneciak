"""Filtri di rischio aggiuntivi, da controllare prima di aprire la
posizione. Vedi STRATEGY.md 2.5. Nessuno di questi è un divieto assoluto: il
corso li descrive come aumento/diminuzione del rischio percepito, da
valutare insieme agli altri fattori."""
import logging
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from common import config
from short_term.indicators import macd

log = logging.getLogger("bot")


def _swing_points(series: pd.Series, order: int = 3) -> list[tuple[int, float]]:
    points = []
    values = series.to_numpy()
    for i in range(order, len(values) - order):
        window = values[i - order : i + order + 1]
        if values[i] == window.max() or values[i] == window.min():
            points.append((i, values[i]))
    return points


@dataclass
class SupportResistanceCheck:
    nearest_level: float | None
    r_multiple_distance: float | None

    @property
    def too_close(self) -> bool:
        if self.r_multiple_distance is None:
            return False
        return self.r_multiple_distance < config.SUPPORT_RESISTANCE_MIN_R_MULTIPLE


def support_resistance_check(
    weekly_df: pd.DataFrame, entry: float, risk_per_share: float, direction: str
) -> SupportResistanceCheck:
    """Cerca il primo livello significativo sul timeframe settimanale sopra
    (long) o sotto (short) l'entrata. 'Significativo' qui è approssimato coi
    massimi/minimi swing settimanali (fractal a 3 barre); il corso lega la
    validità anche a volume e ampiezza del movimento originato, che non sono
    formalizzabili senza gli strumenti proprietari del corso."""
    if risk_per_share <= 0:
        return SupportResistanceCheck(None, None)

    recent = weekly_df.iloc[-(6 * 52) :]  # ~5-6 anni di storico settimanale
    if direction == "long":
        swing_highs = _swing_points(recent["high"], order=3)
        candidates = [v for _, v in swing_highs if v > entry]
        nearest = min(candidates) if candidates else None
    else:
        swing_lows = _swing_points(recent["low"], order=3)
        candidates = [v for _, v in swing_lows if v < entry]
        nearest = max(candidates) if candidates else None

    if nearest is None:
        return SupportResistanceCheck(None, None)

    r_distance = abs(nearest - entry) / risk_per_share
    return SupportResistanceCheck(nearest_level=float(nearest), r_multiple_distance=float(r_distance))


@dataclass
class EarningsCheck:
    next_earnings_date: pd.Timestamp | None
    days_until: int | None

    @property
    def warn(self) -> bool:
        if self.days_until is None:
            return False
        return 0 <= self.days_until <= config.EARNINGS_WARNING_DAYS


def earnings_check(symbol: str) -> EarningsCheck:
    """Best-effort: yfinance non garantisce sempre la prossima data
    trimestrale. In caso di dati mancanti, si assume nessun avviso invece
    di bloccare l'operazione su un dato che potremmo non avere."""
    try:
        calendar = yf.Ticker(symbol).calendar
        next_date = None
        if isinstance(calendar, dict):
            dates = calendar.get("Earnings Date")
            if dates:
                next_date = pd.Timestamp(dates[0] if isinstance(dates, list) else dates)
        elif calendar is not None and "Earnings Date" in getattr(calendar, "index", []):
            next_date = pd.Timestamp(calendar.loc["Earnings Date"].iloc[0])
    except Exception as exc:
        log.warning("Could not fetch earnings calendar for %s: %s", symbol, exc)
        return EarningsCheck(None, None)

    if next_date is None:
        return EarningsCheck(None, None)

    days_until = (next_date.normalize() - pd.Timestamp.now().normalize()).days
    return EarningsCheck(next_earnings_date=next_date, days_until=days_until)


@dataclass
class PriceLevelCheck:
    price: float
    direction: str

    @property
    def blocks_trade(self) -> bool:
        # Unica soglia numerica esplicita nel corso: gli short vanno
        # preferiti sopra $80-100 (poco spazio di ribasso sotto, minimo
        # teorico zero). Per i long il corso non dà un numero preciso
        # ("titoli molto costosi") quindi qui non si applica un filtro
        # rigido, solo quello sugli short.
        if self.direction == "short":
            return self.price < config.SHORT_MIN_PRICE
        return False


def price_level_check(price: float, direction: str) -> PriceLevelCheck:
    return PriceLevelCheck(price=price, direction=direction)


@dataclass
class DivergenceCheck:
    has_divergence: bool
    details: str = ""


def divergence_check(weekly_df: pd.DataFrame, direction: str) -> DivergenceCheck:
    """Divergenza prezzo/istogramma MACD sul settimanale: il prezzo fa un
    nuovo estremo nella direzione del trend ma l'istogramma no."""
    hist = macd(weekly_df["close"])["histogram"]
    if direction == "long":
        price_points = _swing_points(weekly_df["high"], order=2)
    else:
        price_points = _swing_points(weekly_df["low"], order=2)

    if len(price_points) < 2:
        return DivergenceCheck(False)

    (i1, p1), (i2, p2) = price_points[-2], price_points[-1]
    h1, h2 = hist.iloc[i1], hist.iloc[i2]
    if pd.isna(h1) or pd.isna(h2):
        return DivergenceCheck(False)

    if direction == "long":
        diverges = p2 > p1 and h2 < h1
    else:
        diverges = p2 < p1 and h2 > h1

    return DivergenceCheck(
        has_divergence=bool(diverges),
        details="prezzo in nuovo estremo, istogramma MACD no" if diverges else "",
    )
