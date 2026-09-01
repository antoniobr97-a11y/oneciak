"""CLI unico per entrambe le strategie (vedi STRATEGY.md).

Lungo termine (report/esecuzione manuale, revisione mensile o meno):
    python bot.py long-term-status
    python bot.py long-term-pac --deposit 500 [--strategy harry_browne|advanced] [--execute]

Breve termine (screening quotidiano + gestione posizioni aperte):
    python bot.py short-term-screen
    python bot.py short-term-once [--execute]
    python bot.py schedule            # short-term-once ogni giorno feriale a RUN_TIME

--execute invia ordini reali (paper trading) al broker; senza, i comandi
stampano solo un report -- nessun ordine viene inviato.
"""
import argparse
import logging
import math

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from common import config
from common.broker import Broker
from common.data import get_daily_bars, get_monthly_bars
from common.logger_setup import setup_logging
from long_term import advanced_portfolio, harry_browne, pac, risk_profile
from short_term import levels as levels_mod
from short_term import money_management
from short_term.screener import Candidate, screen_universe

log = logging.getLogger("bot")


# --- Lungo termine ----------------------------------------------------------

def cmd_long_term_status(args: argparse.Namespace) -> None:
    prices = {t: float(get_daily_bars(t, period="5d")["close"].iloc[-1]) for t in config.HARRY_BROWNE_TICKERS}
    targets = harry_browne.target_shares(config.LONG_TERM_CAPITAL, prices)
    print(f"\n=== Harry Browne (capitale ${config.LONG_TERM_CAPITAL:,.0f}) ===")
    for ticker, qty in targets.items():
        print(f"  {ticker}: {qty} quote (~${qty * prices[ticker]:,.2f}) @ ${prices[ticker]:.2f}")

    weights = risk_profile.advanced_target_weights()
    print(f"\n=== Advanced -- pesi target (profilo score={config.LONG_TERM_RISK_SCORE}) ===")
    for asset_class, weight in weights.items():
        print(f"  {asset_class}: {weight * 100:.1f}%")

    print("\nSegnale mensile SMA10 per asset (Advanced):")
    for asset_class, ticker in zip(advanced_portfolio.ASSET_CLASSES, config.ADVANCED_TICKERS):
        monthly = get_monthly_bars(ticker, period="10y")["close"]
        signal = advanced_portfolio.monthly_signal(monthly)
        print(f"  {asset_class} ({ticker}): {signal.action} -- {signal.reason}")


def cmd_long_term_pac(args: argparse.Namespace) -> None:
    strategy = args.strategy
    broker = Broker() if args.execute else None

    if strategy == "harry_browne":
        tickers = config.HARRY_BROWNE_TICKERS
        target_weights = {t: harry_browne.WEIGHT_PER_ASSET for t in tickers}
        current_value = {t: 0.0 for t in tickers}
        if broker is not None:
            for t in tickers:
                pos = broker.get_open_position(t)
                if pos:
                    current_value[t] = pos["qty"] * (pos["current_price"] or pos["avg_entry_price"])
        prices = {t: float(get_daily_bars(t, period="5d")["close"].iloc[-1]) for t in tickers}
    else:
        tickers = config.ADVANCED_TICKERS
        weights_by_class = risk_profile.advanced_target_weights()
        target_weights = dict(zip(tickers, weights_by_class.values()))
        current_value = {t: 0.0 for t in tickers}
        if broker is not None:
            for t in tickers:
                pos = broker.get_open_position(t)
                if pos:
                    current_value[t] = pos["qty"] * (pos["current_price"] or pos["avg_entry_price"])
        prices = {t: float(get_daily_bars(t, period="5d")["close"].iloc[-1]) for t in tickers}

    orders = pac.pac_buy_orders(args.deposit, current_value, target_weights, prices)

    print(f"\n=== PAC {strategy}: versamento ${args.deposit:,.2f} ===")
    for ticker, qty in orders.items():
        if qty <= 0:
            continue
        print(f"  BUY {ticker}: {qty} quote (~${qty * prices[ticker]:,.2f}) @ ${prices[ticker]:.2f}")
        if broker is not None:
            broker.buy_market(ticker, qty)

    if not args.execute:
        print("\n(report only -- passa --execute per inviare gli ordini in paper trading)")


# --- Breve termine -----------------------------------------------------------

def _print_candidate(c: Candidate) -> None:
    print(f"\n{c.symbol} {c.direction.upper()} -- {c.pattern} (trend score {c.trend.score}/6)")
    print(f"  entrata={c.levels.entry:.2f} stop={c.levels.stop_loss:.2f} rischio/az={c.levels.risk_per_share:.2f}")
    print(f"  size={c.qty} azioni  settore={c.sector_etf or 'n/d'} (conferma={'si' if c.sector_passes else 'no'})")
    for note in c.notes:
        print(f"  ! {note}")


def cmd_short_term_screen(args: argparse.Namespace) -> None:
    open_positions_count = 0
    if args.execute:
        broker = Broker()
        open_positions_count = len(broker.list_open_positions())

    candidates = screen_universe(open_positions_count=open_positions_count)
    if not candidates:
        print("Nessun candidato trovato.")
        return
    for c in candidates:
        _print_candidate(c)


def manage_open_short_term_positions(broker: Broker) -> None:
    """Applica STRATEGY.md 2.4 punto 1 alle posizioni aperte: al
    raggiungimento di 1R, vende metà posizione e sposta lo stop al
    pareggio sul resto. Una volta che lo stop è già al pareggio, la
    posizione è considerata già gestita (nessuna azione ulteriore qui)."""
    for pos in broker.list_open_positions():
        symbol, qty, entry_price, current_price = pos["symbol"], pos["qty"], pos["avg_entry_price"], pos["current_price"]
        if current_price is None or qty == 0:
            continue
        direction = "long" if qty > 0 else "short"

        stop_order = broker.get_open_stop_order(symbol)
        if stop_order is None or stop_order.stop_price is None:
            continue
        stop_price = float(stop_order.stop_price)
        if abs(stop_price - entry_price) < 1e-6:
            continue  # già al pareggio, metà posizione già chiusa

        if levels_mod.reached_1r(current_price, entry_price, stop_price):
            half_qty = math.floor(abs(qty) / 2)
            if half_qty > 0:
                broker.close_partial(symbol, half_qty, direction)
            # Con 1 sola azione half_qty=0 (niente da vendere): lo stop si
            # sposta comunque al pareggio sull'intera posizione, unico modo
            # di applicare la regola "zero rischio dopo 1R" quando la size
            # non è divisibile a metà.
            remaining = abs(qty) - half_qty
            if remaining > 0:
                broker.move_stop_to_breakeven(symbol, remaining, entry_price, direction)


def cmd_short_term_once(args: argparse.Namespace) -> None:
    broker = Broker()
    if not broker.is_market_open():
        log.info("Mercato chiuso, salto il ciclo.")
        return

    manage_open_short_term_positions(broker)

    equity = broker.get_equity()
    open_positions_count = len(broker.list_open_positions())
    candidates = screen_universe(capital=equity, open_positions_count=open_positions_count)

    for c in candidates:
        if not c.is_actionable:
            continue
        if broker.get_open_position(c.symbol) is not None:
            continue  # già in posizione su questo titolo
        if not money_management.can_open_new_position(open_positions_count):
            log.info("Tetto di rischio aggregato raggiunto, salto i candidati restanti.")
            break

        _print_candidate(c)
        if args.execute:
            broker.enter_with_stop(c.symbol, c.qty, c.direction, c.levels.stop_loss)
        # Si incrementa anche in modalità report-only: il candidato mostrato
        # è quello che verrebbe aperto in sequenza rispettando il tetto di
        # rischio aggregato, cosi' l'anteprima riflette cosa accadrebbe con
        # --execute invece di ignorare l'accumulo tra un candidato e l'altro.
        open_positions_count += 1


def cmd_schedule(args: argparse.Namespace) -> None:
    cmd_short_term_once(argparse.Namespace(execute=True))

    hour, minute = (int(x) for x in config.RUN_TIME.split(":"))
    scheduler = BlockingScheduler(timezone="America/New_York")
    scheduler.add_job(
        lambda: cmd_short_term_once(argparse.Namespace(execute=True)),
        CronTrigger(day_of_week="mon-fri", hour=hour, minute=minute),
    )
    log.info("Scheduler avviato: ciclo breve termine ogni giorno feriale alle %s America/New_York.", config.RUN_TIME)
    scheduler.start()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("long-term-status", help="Report allocazione target Harry Browne + Advanced")
    p.set_defaults(func=cmd_long_term_status)

    p = sub.add_parser("long-term-pac", help="Ordini di acquisto per un versamento PAC")
    p.add_argument("--deposit", type=float, required=True)
    p.add_argument("--strategy", choices=["harry_browne", "advanced"], default="harry_browne")
    p.add_argument("--execute", action="store_true")
    p.set_defaults(func=cmd_long_term_pac)

    p = sub.add_parser("short-term-screen", help="Report candidati (nessun ordine)")
    p.add_argument("--execute", action="store_true", help="considera anche le posizioni aperte nel tetto di rischio")
    p.set_defaults(func=cmd_short_term_screen)

    p = sub.add_parser("short-term-once", help="Un ciclo: gestione posizioni aperte + screening + (opzionale) ordini")
    p.add_argument("--execute", action="store_true")
    p.set_defaults(func=cmd_short_term_once)

    p = sub.add_parser("schedule", help="Ciclo breve termine schedulato ogni giorno feriale")
    p.set_defaults(func=cmd_schedule)

    args = parser.parse_args()
    setup_logging()
    args.func(args)


if __name__ == "__main__":
    main()
