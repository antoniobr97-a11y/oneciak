"""Static 'Harry Browne' permanent portfolio: 4 ETF at 25% each, rebalanced
at fixed calendar dates (never on a drift threshold). See STRATEGY.md 1.1."""
import math
from datetime import date

from common import config

WEIGHT_PER_ASSET = 0.25

# Order matches config.HARRY_BROWNE_TICKERS: equity, bond_long, bond_short, gold
ASSET_CLASSES = ["equity", "bond_long", "bond_short", "gold"]


def target_allocation(tickers: list[str] | None = None) -> dict[str, float]:
    tickers = tickers or config.HARRY_BROWNE_TICKERS
    return {ticker: WEIGHT_PER_ASSET for ticker in tickers}


def target_shares(capital: float, prices: dict[str, float], tickers: list[str] | None = None) -> dict[str, int]:
    """floor(capitale * 25% / prezzo_ETF) per ciascun ETF."""
    tickers = tickers or config.HARRY_BROWNE_TICKERS
    return {
        ticker: math.floor(capital * WEIGHT_PER_ASSET / prices[ticker])
        for ticker in tickers
        if ticker in prices and prices[ticker] > 0
    }


def rebalance_orders(
    current_shares: dict[str, float], prices: dict[str, float], capital: float, tickers: list[str] | None = None
) -> dict[str, int]:
    """Positive = buy this many shares, negative = sell this many shares,
    to bring every asset back to 25% of `capital`."""
    targets = target_shares(capital, prices, tickers)
    return {
        ticker: targets[ticker] - int(current_shares.get(ticker, 0))
        for ticker in targets
    }


_FREQUENCY_MONTHS = {"quarterly": 3, "semiannual": 6, "annual": 12}


def is_rebalance_due(last_rebalance: date, today: date, frequency: str | None = None) -> bool:
    frequency = frequency or config.REBALANCE_FREQUENCY
    months = _FREQUENCY_MONTHS[frequency]
    months_elapsed = (today.year - last_rebalance.year) * 12 + (today.month - last_rebalance.month)
    return months_elapsed >= months
