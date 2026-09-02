"""CLI unico per entrambe le strategie (vedi STRATEGY.md).

Lungo termine (report/esecuzione manuale + ciclo automatico):
    python bot.py long-term-status
    python bot.py long-term-pac --deposit 500 [--strategy harry_browne|advanced] [--execute]
    python bot.py long-term-once [--execute]   # ciclo automatico (LONG_TERM_AUTO_STRATEGY)

Breve termine (screening quotidiano + gestione posizioni aperte):
    python bot.py short-term-screen
    python bot.py short-term-once [--execute]
    python bot.py schedule            # short-term-once + long-term-once ogni giorno feriale a RUN_TIME

--execute invia ordini reali (paper trading) al broker; senza, i comandi
stampano solo un report -- nessun ordine viene inviato.
"""
import argparse
import logging
import math
from datetime import date

import pandas as pd
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from common import config, notify, position_state
from common.broker import Broker
from common.data import get_daily_bars, get_monthly_bars
from common.logger_setup import setup_logging
from long_term import advanced_portfolio, harry_browne, pac, risk_profile
from long_term.advanced_portfolio import closed_monthly_closes
from short_term import money_management
from short_term.indicators import sma
from short_term.screener import Candidate, screen_universe

log = logging.getLogger("bot")

# Gli ETF dei portafogli di lungo termine vivono nello stesso conto Alpaca
# delle azioni di breve termine: vanno tenuti fuori dalla gestione a
# scaglioni, dal conteggio del tetto di rischio e dall'equity usata per il
# sizing del breve termine (audit, vedi STRATEGY.md).
LONG_TERM_TICKERS = set(config.HARRY_BROWNE_TICKERS) | set(config.ADVANCED_TICKERS)


def _last_close(symbol: str) -> float:
    return float(get_daily_bars(symbol, period="5d")["close"].iloc[-1])


# --- Lungo termine: report e PAC manuali ---------------------------------------

def cmd_long_term_status(args: argparse.Namespace) -> None:
    prices = {t: _last_close(t) for t in config.HARRY_BROWNE_TICKERS}
    targets = harry_browne.target_shares(config.LONG_TERM_CAPITAL, prices)
    print(f"\n=== Harry Browne (capitale ${config.LONG_TERM_CAPITAL:,.0f}) ===")
    for ticker, qty in targets.items():
        print(f"  {ticker}: {qty} quote (~${qty * prices[ticker]:,.2f}) @ ${prices[ticker]:.2f}")

    weights = risk_profile.advanced_target_weights()
    print(f"\n=== Advanced -- pesi target (profilo score={config.LONG_TERM_RISK_SCORE}) ===")
    for asset_class, weight in weights.items():
        print(f"  {asset_class}: {weight * 100:.1f}%")

    print("\nSegnale mensile SMA10 per asset (Advanced, solo mesi chiusi):")
    for asset_class, ticker in zip(advanced_portfolio.ASSET_CLASSES, config.ADVANCED_TICKERS):
        monthly = closed_monthly_closes(get_monthly_bars(ticker, period="10y")["close"])
        signal = advanced_portfolio.monthly_signal(monthly)
        above = advanced_portfolio.is_above_sma(monthly)
        state = "n/d" if above is None else ("DENTRO (sopra SMA)" if above else "FUORI (sotto SMA)")
        print(f"  {asset_class} ({ticker}): {signal.action} -- {signal.reason} -- stato: {state}")


def cmd_long_term_pac(args: argparse.Namespace) -> None:
    strategy = args.strategy
    broker = Broker() if args.execute else None

    if strategy == "harry_browne":
        tickers = config.HARRY_BROWNE_TICKERS
        target_weights = {t: harry_browne.WEIGHT_PER_ASSET for t in tickers}
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
    prices = {t: _last_close(t) for t in tickers}

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


# --- Lungo termine: ciclo automatico -----------------------------------------

def _advanced_monthly_cycle(broker: Broker, execute: bool, today: date) -> None:
    """Una decisione al mese per asset (STRATEGY.md 1.2): dentro se l'ultima
    chiusura mensile CHIUSA e' sopra la SMA10, fuori se sotto (vedi
    advanced_portfolio.is_above_sma per l'equivalenza con la regola a
    incroci del corso). Idempotente: agisce una sola volta per mese, cosi'
    puo' girare ogni giorno senza ripetersi e senza saltare il mese se il
    server era spento il primo giorno utile."""
    month_key = today.strftime("%Y-%m")
    if position_state.get_meta("advanced_last_month") == month_key:
        log.info("Advanced: mese %s gia' processato, niente da fare.", month_key)
        return

    weights = risk_profile.advanced_target_weights()
    cash_available = broker.get_cash()
    print(f"\n=== Advanced -- ciclo mensile {month_key} (capitale max ${config.LONG_TERM_CAPITAL:,.0f}) ===")

    for asset_class, ticker in zip(advanced_portfolio.ASSET_CLASSES, config.ADVANCED_TICKERS):
        try:
            monthly = closed_monthly_closes(get_monthly_bars(ticker, period="10y")["close"], today)
            desired_in = advanced_portfolio.is_above_sma(monthly)
            if desired_in is None:
                log.warning("Advanced: storico mensile insufficiente per %s, salto.", ticker)
                continue

            pos = broker.get_open_position(ticker)
            holding = pos["qty"] if pos and pos["qty"] > 0 else 0.0

            if desired_in and holding == 0:
                price = _last_close(ticker)
                dollars = min(config.LONG_TERM_CAPITAL * weights[asset_class], cash_available)
                qty = math.floor(dollars / price) if price > 0 else 0
                if qty <= 0:
                    log.info("Advanced: %s (%s) segnala DENTRO ma cassa insufficiente per almeno 1 quota.", asset_class, ticker)
                    continue
                print(f"  BUY {ticker} ({asset_class}): {qty} quote (~${qty * price:,.2f}) -- sopra SMA10 mensile")
                if execute:
                    broker.buy_market(ticker, qty)
                    notify.alert(f"Lungo termine (Advanced): acquistato {ticker} x{qty} ({asset_class})")
                cash_available -= qty * price
            elif not desired_in and holding > 0:
                print(f"  SELL {ticker} ({asset_class}): {int(holding)} quote -- sotto SMA10 mensile")
                if execute:
                    broker.sell_market(ticker, int(holding))
                    notify.alert(f"Lungo termine (Advanced): venduto {ticker} x{int(holding)} ({asset_class})")
            else:
                print(f"  HOLD {ticker} ({asset_class}): {'dentro' if desired_in else 'fuori'}, invariato")
        except Exception:
            log.exception("Advanced: errore su %s (%s), passo al prossimo asset.", ticker, asset_class)
            notify.alert(f"Lungo termine (Advanced): errore su {ticker}", level="error")

    if execute:
        position_state.set_meta("advanced_last_month", month_key)


def _harry_browne_rebalance_cycle(broker: Broker, execute: bool, today: date) -> None:
    """Ribilanciamento al 25% per ETF a data fissa (STRATEGY.md 1.1), mai a
    soglia di scostamento. Idempotente per periodo (REBALANCE_FREQUENCY)
    tramite la data dell'ultimo ribilanciamento salvata nello stato."""
    last = position_state.get_meta("harry_browne_last_rebalance")
    if last and not harry_browne.is_rebalance_due(date.fromisoformat(last), today):
        log.info("Harry Browne: ultimo ribilanciamento %s, il prossimo non e' ancora dovuto.", last)
        return

    tickers = config.HARRY_BROWNE_TICKERS
    prices = {t: _last_close(t) for t in tickers}
    current = {}
    for t in tickers:
        pos = broker.get_open_position(t)
        current[t] = pos["qty"] if pos else 0.0

    orders = harry_browne.rebalance_orders(current, prices, config.LONG_TERM_CAPITAL)
    cash_available = broker.get_cash()
    print(f"\n=== Harry Browne -- ribilanciamento {today.isoformat()} (capitale ${config.LONG_TERM_CAPITAL:,.0f}) ===")

    # Prima le vendite (liberano cassa), poi gli acquisti.
    for ticker, delta in sorted(orders.items(), key=lambda kv: kv[1]):
        try:
            if delta < 0:
                print(f"  SELL {ticker}: {-delta} quote @ ${prices[ticker]:.2f}")
                if execute:
                    broker.sell_market(ticker, -delta)
                cash_available += -delta * prices[ticker]
            elif delta > 0:
                affordable = math.floor(cash_available / prices[ticker]) if prices[ticker] > 0 else 0
                qty = min(delta, affordable)
                if qty <= 0:
                    log.info("Harry Browne: cassa insufficiente per comprare %s, salto.", ticker)
                    continue
                print(f"  BUY {ticker}: {qty} quote @ ${prices[ticker]:.2f}")
                if execute:
                    broker.buy_market(ticker, qty)
                cash_available -= qty * prices[ticker]
            else:
                print(f"  {ticker}: gia' al target, invariato")
        except Exception:
            log.exception("Harry Browne: errore su %s, passo al prossimo ETF.", ticker)
            notify.alert(f"Lungo termine (Harry Browne): errore su {ticker}", level="error")

    if execute:
        position_state.set_meta("harry_browne_last_rebalance", today.isoformat())
        notify.alert(f"Lungo termine (Harry Browne): ribilanciamento eseguito il {today.isoformat()}")


def run_long_term_cycle(broker: Broker, execute: bool, today: date | None = None) -> None:
    today = today or date.today()
    strategy = config.LONG_TERM_AUTO_STRATEGY
    if strategy == "advanced":
        _advanced_monthly_cycle(broker, execute, today)
    elif strategy == "harry_browne":
        _harry_browne_rebalance_cycle(broker, execute, today)
    else:
        log.info("LONG_TERM_AUTO_STRATEGY=none: lungo termine solo a mano, niente da fare.")


def cmd_long_term_once(args: argparse.Namespace) -> None:
    broker = Broker()
    if args.execute and not broker.is_market_open():
        log.info("Mercato chiuso, salto il ciclo di lungo termine.")
        return
    run_long_term_cycle(broker, execute=args.execute)
    if not args.execute:
        print("\n(report only -- passa --execute per inviare gli ordini in paper trading)")


# --- Breve termine -----------------------------------------------------------

def _print_candidate(c: Candidate) -> None:
    print(f"\n{c.symbol} {c.direction.upper()} -- {c.pattern} (trend score {c.trend.score}/6)")
    print(f"  entrata={c.levels.entry:.2f} stop={c.levels.stop_loss:.2f} rischio/az={c.levels.risk_per_share:.2f}")
    print(f"  size={c.qty} azioni  settore={c.sector_etf or 'n/d'} (conferma={'si' if c.sector_passes else 'no'})")
    for note in c.notes:
        print(f"  ! {note}")


def _short_term_positions(broker: Broker) -> list[dict]:
    """Posizioni aperte del solo breve termine (ETF di lungo termine esclusi)."""
    return [p for p in broker.list_open_positions() if p["symbol"] not in LONG_TERM_TICKERS]


def _short_term_equity(broker: Broker) -> float:
    """Equity del conto meno il controvalore degli ETF di lungo termine:
    il rischio % per operazione del breve termine si calcola sul capitale
    del breve termine, non sul totale (come nel backtest)."""
    equity = broker.get_equity()
    long_term_value = sum(
        abs(p["qty"]) * (p["current_price"] or p["avg_entry_price"])
        for p in broker.list_open_positions()
        if p["symbol"] in LONG_TERM_TICKERS
    )
    return max(0.0, equity - long_term_value)


def cmd_short_term_screen(args: argparse.Namespace) -> None:
    open_positions_count = 0
    broker = None
    if args.execute:
        broker = Broker()
        open_positions_count = len(_short_term_positions(broker))

    candidates = screen_universe(open_positions_count=open_positions_count, broker=broker)
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


def _ensure_protective_stop(broker: Broker, symbol: str, qty: float, entry_price: float, direction: str, stage: str, state: dict) -> None:
    """Auto-riparazione: ogni posizione aperta DEVE avere uno stop attivo al
    broker. Se manca (scaduto, cancellato, riemissione fallita in un ciclo
    precedente), lo riemette: allo stop originale se non si e' ancora
    raggiunto 1R, al pareggio dopo. Senza questo controllo un solo stop
    perso lasciava la posizione scoperta a tempo indefinito (audit, vedi
    STRATEGY.md)."""
    if broker.get_open_stop_order(symbol) is not None:
        return
    stop_price = state.get("stop_price") if stage == "entered" else entry_price
    if not stop_price:
        log.error("%s: nessuno stop attivo e nessuno stop originale salvato -- VA MESSO A MANO.", symbol)
        notify.alert(f"{symbol}: posizione SENZA stop e senza livello salvato, intervenire a mano", level="error")
        return
    broker.place_stop(symbol, qty, stop_price, direction)
    log.warning("%s: stop mancante riemesso a %.2f (stadio %s).", symbol, stop_price, stage)
    notify.alert(f"{symbol}: stop mancante riemesso a {stop_price:.2f}", level="warning")


def manage_open_short_term_positions(broker: Broker) -> None:
    """Applica STRATEGY.md 2.4 punto 2 (gestione a scaglioni) alle posizioni
    aperte del breve termine:
      1R -> vende metà posizione, stop a pareggio sul resto
      3R -> vende un'altra quota (30% della size ORIGINALE), stop a
            pareggio riemesso sul nuovo residuo
      resto (~10-20% originale) -> lasciato correre finché il prezzo non
        chiude sotto/sopra la media mobile di lungo periodo (100/200)
    e in ogni caso verifica che uno stop sia attivo (auto-riparazione).

    Il broker non conserva la size originale né lo stadio raggiunto tra un
    ciclo e l'altro -- li traccia common/position_state.py. Ogni posizione
    è isolata in un try/except: un errore su un singolo titolo (blip di
    rete, ordine rifiutato) non deve impedire la gestione delle altre
    posizioni aperte nello stesso ciclo."""
    open_positions = _short_term_positions(broker)
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
            acted = False

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
                notify.alert(f"{symbol}: 1R raggiunto, chiusa meta' posizione, stop a pareggio")
                acted = True

            elif stage == "1R_done" and r_now >= SECOND_SCALE_OUT_R:
                target = min(abs_qty - original_qty * RUNNER_FRACTION, original_qty * SECOND_SCALE_OUT_FRACTION)
                qty_to_close = max(0, math.floor(target))
                if qty_to_close > 0:
                    broker.close_partial(symbol, qty_to_close, direction)
                # Lo stop a pareggio va riemesso sul NUOVO residuo: quello
                # precedente (cancellato da close_partial) era per la
                # quantità pre-3R e non coprirebbe correttamente il runner.
                remaining = abs_qty - qty_to_close
                if remaining > 0:
                    broker.move_stop_to_breakeven(symbol, remaining, entry_price, direction)
                position_state.set_fields(symbol, stage="3R_done")
                notify.alert(f"{symbol}: 3R raggiunto, chiusa seconda quota, runner in corsa")
                acted = True

            elif stage == "3R_done":
                bars = get_daily_bars(symbol, period="1y")
                long_ma = sma(bars["close"], LONG_TERM_MA_PERIOD)
                if len(long_ma) and not pd.isna(long_ma.iloc[-1]):
                    last_close = float(bars["close"].iloc[-1])
                    reversed_trend = last_close < long_ma.iloc[-1] if direction == "long" else last_close > long_ma.iloc[-1]
                    if reversed_trend:
                        broker.flatten(symbol)
                        position_state.clear(symbol)
                        notify.alert(f"{symbol}: runner chiuso per inversione sulla SMA{LONG_TERM_MA_PERIOD}")
                        acted = True

            if not acted:
                _ensure_protective_stop(broker, symbol, abs_qty, entry_price, direction, stage, state)
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

    equity = _short_term_equity(broker)
    open_positions_count = len(_short_term_positions(broker))
    candidates = screen_universe(capital=equity, open_positions_count=open_positions_count, broker=broker)

    # Nessuna leva: la size e' limitata alla cassa davvero disponibile
    # (decrementata man mano nel ciclo), come nel backtest storico. Il
    # conto paper Alpaca ha margine di default e accetterebbe ordini oltre
    # la cassa -- non e' il profilo di rischio scelto (STRATEGY.md).
    cash_available = broker.get_cash()

    for c in candidates:
        if not c.is_actionable:
            continue
        if broker.get_open_position(c.symbol) is not None:
            continue  # già in posizione su questo titolo
        if not money_management.can_open_new_position(open_positions_count):
            log.info("Tetto di rischio aggregato raggiunto, salto i candidati restanti.")
            break

        qty = c.qty
        if c.levels.entry > 0:
            qty = min(qty, math.floor(cash_available / c.levels.entry))
        if qty <= 0:
            log.info("Cassa insufficiente per %s (serve ~%.2f/azione), salto.", c.symbol, c.levels.entry)
            continue

        _print_candidate(c)
        if qty < c.qty:
            print(f"  ! size ridotta a {qty} per limite di cassa (no leva)")

        opened = True
        if args.execute:
            # Isolato: un ordine rifiutato/un errore di rete su UN titolo
            # non deve impedire di provare i candidati successivi nello
            # stesso ciclo.
            try:
                broker.enter_with_stop(c.symbol, qty, c.direction, c.levels.stop_loss)
                # Salvato per la gestione a scaglioni (1R/3R/runner) e per
                # l'auto-riparazione dello stop nei cicli successivi: il
                # broker non conserva size originale, rischio per azione
                # ne' (se lo stop scade/sparisce) il livello di stop.
                position_state.set_fields(
                    c.symbol,
                    original_qty=qty,
                    risk_per_share=c.levels.risk_per_share,
                    stop_price=c.levels.stop_loss,
                    stage="entered",
                )
                notify.alert(f"Aperta posizione {c.direction.upper()} {c.symbol} x{qty} ({c.pattern})")
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
            cash_available -= qty * c.levels.entry


def _run_cycle_safely() -> None:
    """Un ciclo schedulato non deve mai propagare un'eccezione: un guasto
    sistemico (broker irraggiungibile, errore imprevisto) va notificato e
    registrato, non deve far morire lo scheduler o saltare i cicli futuri.
    Breve e lungo termine sono isolati l'uno dall'altro."""
    try:
        cmd_short_term_once(argparse.Namespace(execute=True))
    except Exception:
        log.exception("Ciclo breve termine fallito.")
        notify.alert("Ciclo breve termine fallito, controlla i log", level="error")
    try:
        cmd_long_term_once(argparse.Namespace(execute=True))
    except Exception:
        log.exception("Ciclo lungo termine fallito.")
        notify.alert("Ciclo lungo termine fallito, controlla i log", level="error")


def cmd_schedule(args: argparse.Namespace) -> None:
    notify.alert("Bot avviato, scheduler attivo")
    _run_cycle_safely()

    hour, minute = (int(x) for x in config.RUN_TIME.split(":"))
    scheduler = BlockingScheduler(timezone="America/New_York")
    scheduler.add_job(
        _run_cycle_safely,
        CronTrigger(day_of_week="mon-fri", hour=hour, minute=minute),
    )
    log.info(
        "Scheduler avviato: ciclo breve + lungo termine (%s) ogni giorno feriale alle %s America/New_York.",
        config.LONG_TERM_AUTO_STRATEGY, config.RUN_TIME,
    )
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

    p = sub.add_parser("long-term-once", help="Ciclo automatico di lungo termine (LONG_TERM_AUTO_STRATEGY)")
    p.add_argument("--execute", action="store_true")
    p.set_defaults(func=cmd_long_term_once)

    p = sub.add_parser("short-term-screen", help="Report candidati (nessun ordine)")
    p.add_argument("--execute", action="store_true", help="considera anche le posizioni aperte nel tetto di rischio")
    p.set_defaults(func=cmd_short_term_screen)

    p = sub.add_parser("short-term-once", help="Un ciclo: gestione posizioni aperte + screening + (opzionale) ordini")
    p.add_argument("--execute", action="store_true")
    p.set_defaults(func=cmd_short_term_once)

    p = sub.add_parser("schedule", help="Ciclo breve + lungo termine schedulato ogni giorno feriale")
    p.set_defaults(func=cmd_schedule)

    args = parser.parse_args()
    setup_logging()
    args.func(args)


if __name__ == "__main__":
    main()
