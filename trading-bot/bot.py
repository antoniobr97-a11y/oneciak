"""Paper-trading bot main loop.

For each symbol in the watchlist, once per trading day (see RUN_TIME in
.env): pull recent daily bars, compute the strategy signal off the latest
closed bar, and act on it:
  - BUY signal + no open position  -> submit a risk-sized bracket order
    (entry + stop-loss + take-profit)
  - SELL signal + open position    -> close the position
  - HOLD                           -> do nothing

Usage:
    python bot.py --once     # run a single cycle right now and exit
    python bot.py            # run once now, then on a daily schedule (RUN_TIME)
"""
import argparse
import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from broker import Broker
from live_data import get_recent_daily_bars
from logger_setup import setup_logging
from strategy import add_indicators, generate_signal

log = logging.getLogger("bot")


def run_cycle(broker: Broker) -> None:
    if not broker.is_market_open():
        log.info("Market is closed, skipping cycle.")
        return

    equity = broker.get_equity()
    log.info("Starting cycle. Account equity: $%.2f", equity)

    for symbol in config.WATCHLIST:
        try:
            process_symbol(broker, symbol, equity)
        except Exception:
            log.exception("Error processing %s", symbol)


def process_symbol(broker: Broker, symbol: str, equity: float) -> None:
    df = add_indicators(get_recent_daily_bars(symbol))
    qty_held = broker.get_open_position_qty(symbol)
    signal = generate_signal(df, has_open_position=qty_held > 0)

    log.info("%s: %s (price=%.2f) -- %s", symbol, signal.action, signal.price, signal.reason)

    if signal.action == "BUY" and qty_held == 0:
        from risk import position_size

        qty = position_size(equity, signal.price, signal.stop_price)
        broker.buy_with_bracket(symbol, qty, signal.stop_price, signal.target_price)
    elif signal.action == "SELL" and qty_held > 0:
        broker.flatten(symbol)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the paper-trading bot.")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit.")
    args = parser.parse_args()

    setup_logging()
    config.require_alpaca_keys()
    broker = Broker()

    if args.once:
        run_cycle(broker)
        return

    run_cycle(broker)  # run immediately once, then on schedule

    hour, minute = (int(x) for x in config.RUN_TIME.split(":"))
    scheduler = BlockingScheduler(timezone="America/New_York")
    scheduler.add_job(
        run_cycle,
        CronTrigger(day_of_week="mon-fri", hour=hour, minute=minute),
        args=[broker],
    )
    log.info("Scheduler started. Will run daily at %s America/New_York on trading days.", config.RUN_TIME)
    scheduler.start()


if __name__ == "__main__":
    main()
