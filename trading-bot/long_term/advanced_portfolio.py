"""Dynamic 'Advanced' portfolio: 5 asset classes, monthly SMA(10)
trend-following in/out signal per asset, risk-profile-based target weights
(risk_profile.py). See STRATEGY.md 1.2."""
import math
from dataclasses import dataclass

import pandas as pd

from common import config
from short_term.indicators import sma

ASSET_CLASSES = ["equity", "bond_long", "bond_short", "gold", "real_estate"]


@dataclass
class MonthlySignal:
    action: str  # "BUY", "SELL", "HOLD"
    reason: str


def monthly_signal(monthly_closes: pd.Series, sma_period: int | None = None) -> MonthlySignal:
    """Regola (timeframe mensile, SMA 10):
    BUY  se il prezzo era sotto la SMA, la incrocia dal basso E la chiusura
         mensile risulta sopra la SMA
    SELL se il prezzo era sopra la SMA, la incrocia dall'alto E la chiusura
         mensile risulta sotto la SMA
    Altrimenti HOLD (si mantiene la posizione corrente, dentro se dentro,
    fuori se fuori) -- il chiamante decide cosa significa "mantenere" in
    base alla posizione che ha aperta.
    """
    period = sma_period or config.ADVANCED_SMA_PERIOD
    sma_series = sma(monthly_closes, period)

    if len(monthly_closes) < period + 2 or pd.isna(sma_series.iloc[-1]) or pd.isna(sma_series.iloc[-2]):
        return MonthlySignal("HOLD", "not enough monthly history")

    prev_close, prev_sma = monthly_closes.iloc[-2], sma_series.iloc[-2]
    last_close, last_sma = monthly_closes.iloc[-1], sma_series.iloc[-1]

    was_below = prev_close < prev_sma
    was_above = prev_close > prev_sma
    now_above = last_close > last_sma
    now_below = last_close < last_sma

    if was_below and now_above:
        return MonthlySignal("BUY", f"chiusura mensile {last_close:.2f} incrocia sopra SMA{period} {last_sma:.2f}")
    if was_above and now_below:
        return MonthlySignal("SELL", f"chiusura mensile {last_close:.2f} incrocia sotto SMA{period} {last_sma:.2f}")
    return MonthlySignal("HOLD", "nessun incrocio pulito questo mese")


def target_dollar_allocation(
    capital: float,
    target_weights: dict[str, float],
    in_position: dict[str, bool],
) -> dict[str, float]:
    """Dollari da allocare per asset class: 0 se il segnale mensile tiene
    l'asset fuori mercato, altrimenti capital * peso_target. Il capitale non
    allocato resta cash (nessuno spostamento verso asset diversi solo
    perché segnalano BUY prima -- regola rigida di STRATEGY.md 1.2)."""
    return {
        asset_class: (capital * target_weights.get(asset_class, 0.0) if in_position.get(asset_class) else 0.0)
        for asset_class in ASSET_CLASSES
    }


def target_shares(dollar_allocation: dict[str, float], prices: dict[str, float]) -> dict[str, int]:
    return {
        asset_class: math.floor(dollars / prices[asset_class])
        for asset_class, dollars in dollar_allocation.items()
        if asset_class in prices and prices[asset_class] > 0
    }
