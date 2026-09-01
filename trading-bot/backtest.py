"""Simple event-driven backtester.

Runs the strategy bar-by-bar over historical daily data for each symbol in
the watchlist independently (each symbol gets its own starting capital --
this keeps the simulation simple; it does not model shared portfolio
capital or correlation across symbols). Prints a performance summary per
symbol.

Usage:
    python backtest.py                 # backtest config.WATCHLIST, 2y of data
    python backtest.py AAPL MSFT -p 5y
"""
import argparse

import numpy as np
import pandas as pd

import config
import risk
from data import get_daily_bars
from strategy import Signal, add_indicators, generate_signal

STARTING_CASH = 10_000.0


def run_backtest(symbol: str, period: str = "2y", starting_cash: float = STARTING_CASH) -> dict:
    df = add_indicators(get_daily_bars(symbol, period=period))

    cash = starting_cash
    shares = 0
    entry_price = 0.0
    stop_price = 0.0
    target_price = 0.0
    equity_curve = []
    trades = []

    min_bars = config.SMA_SLOW + 2
    for i in range(min_bars, len(df)):
        window = df.iloc[: i + 1]
        price = float(window["close"].iloc[-1])
        has_position = shares > 0

        signal: Signal = generate_signal(window, has_position)

        if has_position:
            low = float(window["low"].iloc[-1])
            high = float(window["high"].iloc[-1])
            exit_price = None
            exit_reason = None
            if low <= stop_price:
                exit_price, exit_reason = stop_price, "stop-loss"
            elif high >= target_price:
                exit_price, exit_reason = target_price, "take-profit"
            elif signal.action == "SELL":
                exit_price, exit_reason = price, "trend exit"

            if exit_price is not None:
                cash += shares * exit_price
                trades.append(
                    {
                        "entry": entry_price,
                        "exit": exit_price,
                        "pnl": (exit_price - entry_price) * shares,
                        "reason": exit_reason,
                        "date": window.index[-1],
                    }
                )
                shares = 0

        elif signal.action == "BUY":
            qty = risk.position_size(cash, signal.price, signal.stop_price)
            if qty > 0:
                shares = qty
                entry_price = signal.price
                stop_price = signal.stop_price
                target_price = signal.target_price
                cash -= shares * entry_price

        mark_to_market = cash + shares * price
        equity_curve.append(mark_to_market)

    equity = pd.Series(equity_curve, index=df.index[min_bars:len(df)])
    return summarize(symbol, equity, trades, starting_cash)


def summarize(symbol: str, equity: pd.Series, trades: list, starting_cash: float) -> dict:
    final_equity = float(equity.iloc[-1]) if len(equity) else starting_cash
    total_return_pct = (final_equity / starting_cash - 1) * 100

    daily_returns = equity.pct_change().dropna()
    sharpe = 0.0
    if daily_returns.std() > 0:
        sharpe = float(daily_returns.mean() / daily_returns.std() * np.sqrt(252))

    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_drawdown_pct = float(drawdown.min() * 100) if len(drawdown) else 0.0

    wins = [t for t in trades if t["pnl"] > 0]
    win_rate = (len(wins) / len(trades) * 100) if trades else 0.0

    return {
        "symbol": symbol,
        "final_equity": final_equity,
        "total_return_pct": total_return_pct,
        "num_trades": len(trades),
        "win_rate_pct": win_rate,
        "max_drawdown_pct": max_drawdown_pct,
        "sharpe": sharpe,
    }


def print_report(result: dict) -> None:
    print(f"\n=== {result['symbol']} ===")
    print(f"  Final equity:     ${result['final_equity']:,.2f}")
    print(f"  Total return:     {result['total_return_pct']:+.2f}%")
    print(f"  Trades:           {result['num_trades']} (win rate {result['win_rate_pct']:.1f}%)")
    print(f"  Max drawdown:     {result['max_drawdown_pct']:.2f}%")
    print(f"  Sharpe (approx.): {result['sharpe']:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest the SMA/RSI strategy.")
    parser.add_argument("symbols", nargs="*", default=config.WATCHLIST)
    parser.add_argument("-p", "--period", default="2y", help="yfinance period, e.g. 1y, 2y, 5y")
    args = parser.parse_args()

    print(f"Backtesting {args.symbols} over period={args.period}, starting cash ${STARTING_CASH:,.0f} each\n")
    for symbol in args.symbols:
        try:
            result = run_backtest(symbol, period=args.period)
            print_report(result)
        except Exception as exc:
            print(f"\n=== {symbol} ===\n  Failed: {exc}")


if __name__ == "__main__":
    main()
