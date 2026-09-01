"""Thin wrapper around Alpaca's trading API (paper by default -- see
config.ALPACA_PAPER / .env). Handles: account/position lookups, market-hours
check, and submitting risk-managed bracket orders (entry + stop-loss +
take-profit in one call)."""
import logging

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import (
    MarketOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)

import config

log = logging.getLogger("bot")


class Broker:
    def __init__(self) -> None:
        config.require_alpaca_keys()
        self.client = TradingClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY, paper=config.ALPACA_PAPER)
        if not config.ALPACA_PAPER:
            log.warning("ALPACA_PAPER=false -- this bot will trade with REAL MONEY.")

    def is_market_open(self) -> bool:
        return bool(self.client.get_clock().is_open)

    def get_equity(self) -> float:
        return float(self.client.get_account().equity)

    def get_open_position_qty(self, symbol: str) -> float:
        try:
            pos = self.client.get_open_position(symbol)
            return float(pos.qty)
        except Exception:
            return 0.0

    def buy_with_bracket(self, symbol: str, qty: int, stop_price: float, target_price: float):
        if qty <= 0:
            log.info("Skipping %s: computed position size is 0.", symbol)
            return None

        order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            stop_loss=StopLossRequest(stop_price=round(stop_price, 2)),
            take_profit=TakeProfitRequest(limit_price=round(target_price, 2)),
        )
        result = self.client.submit_order(order)
        log.info(
            "BUY submitted: %s qty=%s stop=%.2f target=%.2f order_id=%s",
            symbol, qty, stop_price, target_price, result.id,
        )
        return result

    def flatten(self, symbol: str):
        try:
            result = self.client.close_position(symbol)
            log.info("SELL submitted (flatten position): %s", symbol)
            return result
        except Exception as exc:
            log.warning("Could not close position for %s: %s", symbol, exc)
            return None
