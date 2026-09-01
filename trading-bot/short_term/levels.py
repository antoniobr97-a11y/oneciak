"""Calcolo dei livelli di entrata/stop-loss e gestione della posizione dopo
l'ingresso. Vedi STRATEGY.md 2.4."""
from dataclasses import dataclass

import pandas as pd

from common import config
from short_term.indicators import avg_daily_range


@dataclass
class EntryLevels:
    direction: str
    entry: float
    stop_loss: float
    risk_per_share: float


def compute_levels(setup_bar: pd.Series, volatility: float, direction: str) -> EntryLevels:
    """
    LONG:
      entrata   = chiusura(barra_di_setup) + volatilità
                  (se cade dentro il range della barra, spostare appena
                  sopra il massimo)
      stop_loss = minimo(barra_di_setup) - volatilità

    SHORT (speculare):
      entrata   = chiusura(barra_di_setup) - volatilità
      stop_loss = massimo(barra_di_setup) + volatilità
    """
    if direction == "long":
        entry = setup_bar["close"] + volatility
        if entry <= setup_bar["high"]:
            entry = setup_bar["high"] + 0.01
        stop_loss = setup_bar["low"] - volatility
    else:
        entry = setup_bar["close"] - volatility
        if entry >= setup_bar["low"]:
            entry = setup_bar["low"] - 0.01
        stop_loss = setup_bar["high"] + volatility

    risk_per_share = abs(entry - stop_loss)
    return EntryLevels(direction=direction, entry=entry, stop_loss=stop_loss, risk_per_share=risk_per_share)


def levels_for_setup_bar(df: pd.DataFrame, setup_bar_index: int, direction: str, period: int | None = None) -> EntryLevels:
    period = period or config.VOLATILITY_PERIOD
    volatility_series = avg_daily_range(df["high"], df["low"], period)
    volatility = volatility_series.iloc[setup_bar_index]
    if pd.isna(volatility):
        volatility = (df["high"] - df["low"]).iloc[: setup_bar_index + 1].mean()
    return compute_levels(df.iloc[setup_bar_index], float(volatility), direction)


# --- Gestione della posizione dopo l'ingresso (STRATEGY.md 2.4, punto 4) ---

def r_multiple(current_price: float, entry: float, stop_loss: float) -> float:
    risk = abs(entry - stop_loss)
    if risk == 0:
        return 0.0
    direction = 1 if entry > stop_loss else -1
    return direction * (current_price - entry) / risk


def target_price_at_r(entry: float, risk_per_share: float, r: float, direction: str) -> float:
    sign = 1 if direction == "long" else -1
    return entry + sign * r * risk_per_share


def reached_1r(current_price: float, entry: float, stop_loss: float) -> bool:
    """1R: rischio/beneficio 1:1 raggiunto -> vendere metà posizione,
    spostare lo stop al pareggio sul resto."""
    return r_multiple(current_price, entry, stop_loss) >= 1.0


def breakeven_stop(entry: float) -> float:
    return entry
