"""Position sizing: risk a fixed % of equity per trade, sized off the
distance to the stop-loss, capped at a max % of equity per position."""
import math

import config


def position_size(equity: float, entry_price: float, stop_price: float) -> int:
    if entry_price <= 0 or stop_price >= entry_price:
        return 0

    risk_amount = equity * (config.RISK_PER_TRADE_PCT / 100)
    stop_distance = entry_price - stop_price
    shares_by_risk = risk_amount / stop_distance

    max_position_value = equity * (config.MAX_POSITION_PCT / 100)
    shares_by_cap = max_position_value / entry_price

    shares = min(shares_by_risk, shares_by_cap)
    return max(0, math.floor(shares))
