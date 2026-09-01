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

import pandas as pd
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from common import config, notify, position_state
from common.broker import Broker
from common.data import get_daily_bars, get_monthly_bars
from common.logger_setup import setup_logging
from long_term import advanced_portfolio, harry_browne, pac, risk_profile
from short_term import money_management
from short_term.indicators import sma
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


SECOND_SCALE_OUT_R = 3.0  # STRATEGY.md 2.4 punto 2: "valutare la chiusura intorno a 3R/4R"
SECOND_SCALE_OUT_FRACTION = 0.30  # frazione della size ORIGINALE venduta a 3R
RUNNER_FRACTION = 0.20  # quota residua lasciata correre fino al segnale di inversione
LONG_TERM_MA_PERIOD = 200  # SMA lunga per l'uscita del "runner" (il corso cita "tipo 100/200")


def _r_multiple(price: float, entry: float, risk_per_share: float, direction: str) -> float:
    if risk_per_share <= 0:
        return 0.0
    return (price - entry) / risk_per_share if direction == "long" else (entry - price) / risk_per_share


def manage_open_short_term_positions(broker: Broker) -> None:
    """Applica STRATEGY.md 2.4 punto 2 (gestione a scaglioni) alle posizioni
    aperte:
      1R -> vende metà posizione, stop a pareggio sul resto
      3R -> vende un'altra quota (30% della size ORIGINALE)
      resto (~10-20% originale) -> lasciato correre finché il prezzo non
        chiude sotto/sopra la media mobile di lungo periodo (100/200)

    Il broker non conserva la size originale né lo stadio raggiunto tra un
    ciclo e l'altro -- li traccia common/position_state.py. Ogni posizione
    è isolata in un try/except: un errore su un singolo titolo (blip di
    rete, ordine rifiutato) non deve impedire la gestione delle altre
    posizioni aperte nello stesso ciclo."""
    open_positions = broker.list_open_positions()
    open_symbols = {pos["symbol"] for pos in open_positions}

    for pos in open_positions:
        symbol = pos["symbol"]
        try:
            qty, entry_price, current_price = pos["qty"], pos["avg_entry_price"], pos["current_price"]
            if current_price is None or qty == 0:
                continue
            direction = "long" if qty > 0 else "short"
            abs_qty = abs(qty)

            state = position_state.get(symbol)
            risk_per_share = state.get("risk_per_share")
            original_qty = state.get("original_qty", abs_qty)
            stage = state.get("stage", "entered")

            if not risk_per_share:
                # Nessuno stato salvato (posizione aperta prima di questa
                # funzionalità, o file di stato perso): il rischio originale
                # non è più ricostruibile in modo affidabile -- si segnala
                # e si salta, non si inventa un numero su cui poi si
                # baserebbero vendite reali.
                log.warning("Nessuno stato di rischio salvato per %s, gestione a scaglioni saltata (va seguita a mano).", symbol)
                continue

            r_now = _r_multiple(current_price, entry_price, risk_per_share, direction)

            if stage == "entered" and r_now >= 1.0:
                half_qty = math.floor(abs_qty / 2)
                if half_qty > 0:
                    broker.close_partial(symbol, half_qty, direction)
                # Con 1 sola azione half_qty=0 (niente da vendere): lo stop si
                # sposta comunque al pareggio sull'intera posizione, unico modo
                # di applicare la regola "zero rischio dopo 1R" quando la size
                # non è divisibile a metà.
                remaining = abs_qty - half_qty
                if remaining > 0:
                    broker.move_stop_to_breakeven(symbol, remaining, entry_price, direction)
                position_state.set_fields(symbol, stage="1R_done")

            elif stage == "1R_done" and r_now >= SECOND_SCALE_OUT_R:
                target = min(abs_qty - original_qty * RUNNER_FRACTION, original_qty * SECOND_SCALE_OUT_FRACTION)
                qty_to_close = max(0, math.floor(target))
                if qty_to_close > 0:
                    broker.close_partial(symbol, qty_to_close, direction)
                position_state.set_fields(symbol, stage="3R_done")

            elif stage == "3R_done":
                bars = get_daily_bars(symbol, period="1y")
                long_ma = sma(bars["close"], LONG_TERM_MA_PERIOD)
                if len(long_ma) and not pd.isna(long_ma.iloc[-1]):
                    last_close = float(bars["close"].iloc[-1])
                    reversed_trend = last_close < long_ma.iloc[-1] if direction == "long" else last_close > long_ma.iloc[-1]
                    if reversed_trend:
                        broker.flatten(symbol)
                        position_state.clear(symbol)
        except Exception:
            log.exception("Errore gestendo la posizione aperta su %s, salto al prossimo titolo.", symbol)
            notify.alert(f"Errore gestendo la posizione {symbol}", level="error")

    # Pulizia: stato orfano per simboli non più in posizione (chiusi dallo
    # stop del broker, o dall'uscita finale sopra).
    for symbol in position_state.tracked_symbols():
        if symbol not in open_symbols:
            position_state.clear(symbol)


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
        opened = True
        if args.execute:
            # Isolato: un ordine rifiutato/un errore di rete su UN titolo
            # non deve impedire di provare i candidati successivi nello
            # stesso ciclo.
            try:
                broker.enter_with_stop(c.symbol, c.qty, c.direction, c.levels.stop_loss)
                # Salvato per la gestione a scaglioni (1R/3R/runner) nei
                # cicli successivi: il broker non conserva la size
                # originale né il rischio per azione tra un ordine e l'altro.
                position_state.set_fields(
                    c.symbol, original_qty=c.qty, risk_per_share=c.levels.risk_per_share, stage="entered"
                )
                notify.alert(f"Aperta posizione {c.direction.upper()} {c.symbol} x{c.qty} ({c.pattern})")
            except Exception:
                log.exception("Errore inviando l'ordine per %s, salto al prossimo candidato.", c.symbol)
                notify.alert(f"Errore inviando l'ordine per {c.symbol}", level="error")
                opened = False

        # Si incrementa anche in modalità report-only (candidato che
        # verrebbe aperto in sequenza rispettando il tetto di rischio
        # aggregato, cosi' l'anteprima riflette cosa accadrebbe con
        # --execute) -- ma NON se l'invio ordine e' effettivamente fallito,
        # altrimenti il tetto di rischio conterebbe una posizione mai aperta.
        if opened:
            open_positions_count += 1


def _run_cycle_safely() -> None:
    """Un ciclo schedulato non deve mai propagare un'eccezione: un guasto
    sistemico (broker irraggiungibile, errore imprevisto) va notificato e
    registrato, non deve far morire lo scheduler o saltare i cicli futuri."""
    try:
        cmd_short_term_once(argparse.Namespace(execute=True))
    except Exception:
        log.exception("Ciclo breve termine fallito.")
        notify.alert("Ciclo breve termine fallito, controlla i log", level="error")


def cmd_schedule(args: argparse.Namespace) -> None:
    notify.alert("Bot avviato, scheduler attivo")
    _run_cycle_safely()

    hour, minute = (int(x) for x in config.RUN_TIME.split(":"))
    scheduler = BlockingScheduler(timezone="America/New_York")
    scheduler.add_job(
        _run_cycle_safely,
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
