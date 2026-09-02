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


def _pending_symbols() -> list[str]:
    return [s for s in position_state.tracked_symbols() if position_state.get(s).get("stage") == "pending"]


def cmd_short_term_screen(args: argparse.Namespace) -> None:
    open_positions_count = 0
    broker = None
    if args.execute:
        broker = Broker()
        open_positions_count = len(_short_term_positions(broker)) + len(_pending_symbols())

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


def _target(entry: float, risk_per_share: float, r: float, direction: str) -> float:
    return entry + r * risk_per_share if direction == "long" else entry - r * risk_per_share


def _tranches(original_qty: int) -> tuple[int, int, int]:
    """(meta' venduta a T1=1R, quota venduta a 3R, runner) dalla size
    originale -- stessa aritmetica del backtest v3+: meta' a 1R, poi il 30%
    dell'originale a 3R, il resto (~20%) corre fino all'inversione."""
    half = math.floor(original_qty / 2)
    remaining = original_qty - half
    second = max(0, math.floor(min(remaining - original_qty * RUNNER_FRACTION, original_qty * SECOND_SCALE_OUT_FRACTION)))
    runner = remaining - second
    return half, second, runner


def _place_entered_structure(broker, symbol, direction, abs_qty, entry, risk, stop_price, half) -> None:
    """Stadio 'entered' (corso, video 44 scenario A/B): sulla meta' da
    vendere a T1 un OCO (sell limit a entrata+1R / sell stop allo stop
    iniziale); sull'altra meta' un sell stop allo stop iniziale. Se il
    prezzo tocca T1 la meta' viene venduta dal limit (come nel backtest,
    che riempie a 1R quando il massimo di giornata lo tocca); se tocca lo
    stop, entrambi gli stop chiudono tutto."""
    broker.cancel_open_orders(symbol)
    oco_qty = min(half, abs_qty)
    rest = abs_qty - oco_qty
    if oco_qty > 0:
        broker.submit_oco_exit(symbol, oco_qty, direction, _target(entry, risk, 1.0, direction), stop_price)
    if rest > 0:
        broker.submit_stop(symbol, rest, stop_price, direction)


def _place_1r_done_structure(broker, symbol, direction, abs_qty, entry, risk, second) -> None:
    """Stadio '1R_done': stop a pareggio su tutto il residuo; sulla quota
    da vendere a 3R un OCO (sell limit a entrata+3R / sell stop a
    pareggio), sul runner un sell stop a pareggio."""
    broker.cancel_open_orders(symbol)
    oco_qty = min(second, abs_qty)
    rest = abs_qty - oco_qty
    if oco_qty > 0:
        broker.submit_oco_exit(symbol, oco_qty, direction, _target(entry, risk, SECOND_SCALE_OUT_R, direction), entry)
    if rest > 0:
        broker.submit_stop(symbol, rest, entry, direction)


def _place_runner_structure(broker, symbol, direction, abs_qty, entry) -> None:
    """Stadio '3R_done': solo lo stop a pareggio sul runner; l'uscita e'
    decisa dal ciclo giornaliero sull'inversione della SMA200."""
    broker.cancel_open_orders(symbol)
    broker.submit_stop(symbol, abs_qty, entry, direction)


def manage_open_short_term_positions(broker: Broker) -> None:
    """Applica STRATEGY.md 2.4 punto 2 (gestione a scaglioni, corso video
    44/47) alle posizioni aperte del breve termine, con gli ordini di
    uscita SEMPRE presenti al broker (mai un'uscita che dipende dal bot
    che gira quel giorno):
      pending  -> l'ordine d'ingresso stop e' stato eseguito: stadio 'entered'
      entered  -> OCO(meta': limit a 1R / stop iniziale) + stop iniziale sul
                  resto; quando il limit a 1R e' eseguito -> '1R_done'
      1R_done  -> stop a pareggio su tutto: OCO(quota 3R: limit a 3R / stop
                  pareggio) + stop pareggio sul runner; quando il limit a
                  3R e' eseguito -> '3R_done'
      3R_done  -> stop pareggio sul runner; chiusura totale quando il prezzo
                  chiude oltre la SMA200 nella direzione opposta
    A ogni stadio, se al broker non c'e' NESSUN ordine di uscita aperto
    (scaduto, cancellato, riemissione fallita), la struttura viene riemessa
    (auto-riparazione). Il broker non conserva size originale, rischio per
    azione e stadio: li traccia common/position_state.py. Ogni posizione e'
    isolata in un try/except."""
    open_positions = _short_term_positions(broker)
    open_symbols = {pos["symbol"] for pos in open_positions}

    for pos in open_positions:
        symbol = pos["symbol"]
        try:
            qty, entry_price, current_price = pos["qty"], pos["avg_entry_price"], pos["current_price"]
            if qty == 0:
                continue
            direction = "long" if qty > 0 else "short"
            abs_qty = int(abs(qty))

            state = position_state.get(symbol)
            risk = state.get("risk_per_share")
            if not risk:
                # Nessuno stato salvato (posizione aperta a mano o file di
                # stato perso): il rischio originale non e' ricostruibile in
                # modo affidabile -- si segnala e si salta, non si inventa un
                # numero su cui poi si baserebbero ordini reali.
                log.warning("Nessuno stato di rischio salvato per %s, gestione a scaglioni saltata (va seguita a mano).", symbol)
                continue

            stage = state.get("stage", "entered")
            if stage == "pending":
                # L'ordine d'ingresso e' stato eseguito: da qui la size
                # originale e' quella davvero eseguita (non quella pianificata).
                position_state.set_fields(symbol, stage="entered", original_qty=abs_qty)
                notify.alert(f"Eseguito ingresso {direction.upper()} {symbol} x{abs_qty} @ {entry_price:.2f}")
                stage = "entered"
                state = position_state.get(symbol)

            original_qty = int(state.get("original_qty") or abs_qty)
            stop_price = state.get("stop_price")
            half, second, runner = _tranches(original_qty)
            open_orders = broker.list_open_orders(symbol)

            if stage == "entered":
                if half > 0 and abs_qty <= original_qty - half:
                    # T1 eseguito: venduta meta', da qui il resto lavora a rischio zero
                    _place_1r_done_structure(broker, symbol, direction, abs_qty, entry_price, risk, second)
                    position_state.set_fields(symbol, stage="1R_done")
                    notify.alert(f"{symbol}: 1R raggiunto, venduta meta' posizione, stop a pareggio sul resto")
                elif half == 0 and current_price is not None and _r_multiple(current_price, entry_price, risk, direction) >= 1.0:
                    # Size 1: niente da vendere a meta'; lo stop va comunque
                    # al pareggio (unico modo di applicare "zero rischio dopo 1R").
                    _place_runner_structure(broker, symbol, direction, abs_qty, entry_price)
                    position_state.set_fields(symbol, stage="1R_done")
                elif not open_orders:
                    if not stop_price:
                        log.error("%s: nessun ordine di uscita e nessuno stop salvato -- VA MESSO A MANO.", symbol)
                        notify.alert(f"{symbol}: posizione SENZA stop e senza livello salvato, intervenire a mano", level="error")
                        continue
                    _place_entered_structure(broker, symbol, direction, abs_qty, entry_price, risk, stop_price, half)
                    log.warning("%s: ordini di uscita mancanti, riemessi (stop %.2f, T1 %.2f).", symbol, stop_price, _target(entry_price, risk, 1.0, direction))
                    notify.alert(f"{symbol}: ordini di uscita mancanti, riemessi", level="warning")

            elif stage == "1R_done":
                if second > 0 and abs_qty <= runner:
                    _place_runner_structure(broker, symbol, direction, abs_qty, entry_price)
                    position_state.set_fields(symbol, stage="3R_done")
                    notify.alert(f"{symbol}: 3R raggiunto, venduta seconda quota, runner in corsa")
                elif not open_orders:
                    _place_1r_done_structure(broker, symbol, direction, abs_qty, entry_price, risk, second)
                    notify.alert(f"{symbol}: ordini di uscita mancanti, riemessi", level="warning")

            elif stage == "3R_done":
                bars = get_daily_bars(symbol, period="1y")
                long_ma = sma(bars["close"], LONG_TERM_MA_PERIOD)
                reversed_trend = False
                if len(long_ma) and not pd.isna(long_ma.iloc[-1]):
                    last_close = float(bars["close"].iloc[-1])
                    reversed_trend = last_close < long_ma.iloc[-1] if direction == "long" else last_close > long_ma.iloc[-1]
                if reversed_trend:
                    broker.flatten(symbol)
                    position_state.clear(symbol)
                    notify.alert(f"{symbol}: runner chiuso per inversione sulla SMA{LONG_TERM_MA_PERIOD}")
                elif not open_orders:
                    _place_runner_structure(broker, symbol, direction, abs_qty, entry_price)
                    notify.alert(f"{symbol}: stop del runner mancante, riemesso", level="warning")
        except Exception:
            log.exception("Errore gestendo la posizione aperta su %s, salto al prossimo titolo.", symbol)
            notify.alert(f"Errore gestendo la posizione {symbol}", level="error")

    # Pulizia: stato orfano per simboli non piu' in posizione (chiusi dallo
    # stop del broker, o dall'uscita finale sopra) -- ma non gli ingressi
    # pendenti, che non hanno ancora una posizione per definizione.
    for symbol in position_state.tracked_symbols():
        if symbol not in open_symbols and position_state.get(symbol).get("stage") != "pending":
            position_state.clear(symbol)


def reconcile_pending_entries(broker: Broker, candidate_symbols: set[str], today: date) -> None:
    """Gli ordini d'ingresso pendenti (buy stop) restano validi finche' il
    titolo mostra ancora il setup allo screening di oggi -- come nel
    backtest, dove il pendente viene aggiornato o cancellato a ogni
    scansione. Cancellati se il setup non c'e' piu', se l'ordine non e'
    piu' aperto al broker (scaduto/rifiutato) o oltre il tetto di giorni."""
    for symbol in _pending_symbols():
        try:
            if broker.get_open_position(symbol) is not None:
                continue  # eseguito: lo gestisce manage_open_short_term_positions
            state = position_state.get(symbol)
            since = state.get("pending_since")
            expired = bool(since) and (today - date.fromisoformat(since)).days > config.SHORT_TERM_PENDING_MAX_DAYS
            order_alive = len(broker.list_open_orders(symbol)) > 0
            if symbol not in candidate_symbols or expired or not order_alive:
                reason = "setup non piu' valido" if symbol not in candidate_symbols else ("scaduto" if expired else "ordine non piu' aperto")
                broker.cancel_open_orders(symbol)
                position_state.clear(symbol)
                log.info("Ingresso pendente su %s cancellato: %s.", symbol, reason)
        except Exception:
            log.exception("Errore riconciliando l'ingresso pendente su %s.", symbol)


def _drawdown_brake_active(broker: Broker) -> bool:
    """Corso, video 45: drawdown complessivo da tenere entro il 10-15%. Se
    l'equity del conto e' sotto il suo massimo storico di piu' di
    SHORT_TERM_MAX_DRAWDOWN_PCT, niente nuove entrate finche' non recupera
    (le posizioni aperte continuano a essere gestite normalmente)."""
    if config.SHORT_TERM_MAX_DRAWDOWN_PCT <= 0:
        return False
    equity = broker.get_equity()
    peak = max(float(position_state.get_meta("equity_peak", 0.0) or 0.0), equity)
    position_state.set_meta("equity_peak", peak)
    drawdown = 1 - equity / peak if peak > 0 else 0.0
    if drawdown >= config.SHORT_TERM_MAX_DRAWDOWN_PCT / 100:
        log.warning("Freno di drawdown attivo: equity %.0f, massimo %.0f (-%.1f%%). Nessuna nuova entrata.", equity, peak, drawdown * 100)
        notify.alert(f"Freno di drawdown attivo (-{drawdown * 100:.1f}% dal massimo): nessuna nuova entrata", level="warning")
        return True
    return False


def cmd_short_term_once(args: argparse.Namespace) -> None:
    broker = Broker()
    if not broker.is_market_open():
        log.info("Mercato chiuso, salto il ciclo.")
        return
    today = date.today()

    manage_open_short_term_positions(broker)

    equity = _short_term_equity(broker)
    open_positions_count = len(_short_term_positions(broker)) + len(_pending_symbols())
    candidates = screen_universe(capital=equity, open_positions_count=open_positions_count, broker=broker)

    reconcile_pending_entries(broker, {c.symbol for c in candidates if c.is_actionable}, today)
    open_positions_count = len(_short_term_positions(broker)) + len(_pending_symbols())

    if _drawdown_brake_active(broker):
        return

    # Nessuna leva: la size e' limitata alla cassa davvero disponibile
    # (decrementata man mano nel ciclo), come nel backtest storico. Il
    # conto paper Alpaca ha margine di default e accetterebbe ordini oltre
    # la cassa -- non e' il profilo di rischio scelto (STRATEGY.md).
    cash_available = broker.get_cash()

    for c in candidates:
        if not c.is_actionable:
            continue
        if broker.get_open_position(c.symbol) is not None:
            continue  # gia' in posizione su questo titolo

        existing = position_state.get(c.symbol)
        replacing = existing.get("stage") == "pending"
        if replacing:
            same_levels = (
                abs(float(existing.get("entry", 0.0)) - c.levels.entry) < 0.01
                and abs(float(existing.get("stop_price", 0.0)) - c.levels.stop_loss) < 0.01
            )
            if same_levels:
                continue  # stesso setup, ordine gia' in attesa al broker
            # La barra di setup si e' spostata: si sostituisce l'ordine con i nuovi livelli.
        elif not money_management.can_open_new_position(open_positions_count):
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
        if replacing:
            print("  (aggiorna l'ordine d'ingresso pendente con i nuovi livelli)")

        opened = True
        if args.execute:
            # Isolato: un ordine rifiutato/un errore di rete su UN titolo
            # non deve impedire di provare i candidati successivi nello
            # stesso ciclo.
            try:
                if replacing:
                    broker.cancel_open_orders(c.symbol)
                # Corso, video 41: l'ingresso e' un ordine STOP al livello
                # calcolato (chiusura della barra di setup + volatilita'),
                # non un acquisto a mercato: si entra solo se il prezzo
                # supera davvero il livello.
                broker.submit_stop_entry(c.symbol, qty, c.direction, c.levels.entry, c.levels.stop_loss)
                position_state.set_fields(
                    c.symbol,
                    stage="pending",
                    direction=c.direction,
                    entry=c.levels.entry,
                    stop_price=c.levels.stop_loss,
                    risk_per_share=c.levels.risk_per_share,
                    original_qty=qty,
                    pattern=c.pattern,
                    pending_since=existing.get("pending_since") or today.isoformat(),
                )
                notify.alert(f"Ordine d'ingresso {c.direction.upper()} {c.symbol} x{qty} a {c.levels.entry:.2f} (stop {c.levels.stop_loss:.2f}, {c.pattern})")
            except Exception:
                log.exception("Errore inviando l'ordine per %s, salto al prossimo candidato.", c.symbol)
                notify.alert(f"Errore inviando l'ordine per {c.symbol}", level="error")
                opened = False

        # Si incrementa anche in modalita' report-only (candidato che
        # verrebbe messo in attesa rispettando il tetto di rischio
        # aggregato, cosi' l'anteprima riflette cosa accadrebbe con
        # --execute) -- ma NON se l'invio ordine e' effettivamente fallito
        # e NON per un pendente sostituito (gia' contato).
        if opened and not replacing:
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
