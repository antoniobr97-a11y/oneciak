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
import threading
import time
from datetime import date

import pandas as pd
import requests
from alpaca.common.exceptions import APIError
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from common import config, diario, notify, position_state
from common.market_time import MARKET_TIMEZONE, market_now, market_today
from common.broker import Broker, order_type_name
from common.data import get_daily_bars, get_monthly_bars
from common.logger_setup import setup_logging
from long_term import advanced_portfolio, harry_browne, pac, risk_profile
from long_term.advanced_portfolio import closed_monthly_closes
from short_term import money_management, rendiconto, sector
from short_term.indicators import atr, sma
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
    for asset_class, ticker in zip(advanced_portfolio.ASSET_CLASSES, config.ADVANCED_TICKERS, strict=True):
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
        target_weights = dict(zip(tickers, weights_by_class.values(), strict=True))

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

def _advanced_monthly_cycle(
    broker: Broker, execute: bool, today: date, forza: bool = False
) -> None:
    """Una decisione al mese per asset (STRATEGY.md 1.2): dentro se l'ultima
    chiusura mensile CHIUSA e' sopra la SMA10, fuori se sotto (vedi
    advanced_portfolio.is_above_sma per l'equivalenza con la regola a
    incroci del corso). Idempotente: agisce una sola volta per mese, cosi'
    puo' girare ogni giorno senza ripetersi e senza saltare il mese se il
    server era spento il primo giorno utile."""
    month_key = today.strftime("%Y-%m")
    if forza and position_state.get_meta("advanced_last_month") == month_key:
        log.info("Advanced: mese %s gia' processato, ma il ciclo e' FORZATO.", month_key)
    elif position_state.get_meta("advanced_last_month") == month_key:
        log.info("Advanced: mese %s gia' processato, niente da fare.", month_key)
        return

    weights = risk_profile.advanced_target_weights()
    cash_available = broker.get_cash()
    failed = False
    print(f"\n=== Advanced -- ciclo mensile {month_key} (capitale max ${config.LONG_TERM_CAPITAL:,.0f}) ===")

    for asset_class, ticker in zip(advanced_portfolio.ASSET_CLASSES, config.ADVANCED_TICKERS, strict=True):
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
            failed = True

    # Il mese si segna come fatto solo se e' andato tutto a buon fine.
    # Segnandolo comunque, un errore su un asset (rete, ordine rifiutato)
    # lo lascerebbe fuori posizione per un mese intero senza riprovare.
    # Riprovare e' sicuro: la decisione e' ricalcolata sulle posizioni
    # reali, quindi un asset gia' sistemato risulta "invariato".
    if execute and not failed:
        position_state.set_meta("advanced_last_month", month_key)
    elif failed:
        log.warning("Advanced: mese %s NON segnato come completato (errori sopra), si riprova al prossimo ciclo.", month_key)


def _harry_browne_rebalance_cycle(
    broker: Broker, execute: bool, today: date, forza: bool = False
) -> None:
    """Ribilanciamento al 25% per ETF a data fissa (STRATEGY.md 1.1), mai a
    soglia di scostamento. Idempotente per periodo (REBALANCE_FREQUENCY)
    tramite la data dell'ultimo ribilanciamento salvata nello stato."""
    last = position_state.get_meta("harry_browne_last_rebalance")
    if last and forza:
        log.info("Harry Browne: ribilanciamento FORZATO (l'ultimo e' del %s).", last)
    elif last and not harry_browne.is_rebalance_due(date.fromisoformat(last), today):
        log.info("Harry Browne: ultimo ribilanciamento %s, il prossimo non e' ancora dovuto.", last)
        return

    tickers = config.HARRY_BROWNE_TICKERS
    # I prezzi si leggono uno per uno con l'errore isolato. Prima era una
    # sola espressione: bastava che il prezzo di UN ETF non arrivasse
    # perche' l'eccezione uscisse da questa funzione PRIMA del ciclo
    # protetto piu' sotto, quindi senza il log per ETF e senza notifica --
    # il ribilanciamento trimestrale saltava e si vedeva solo come una riga
    # di errore generica.
    prices, missing = {}, []
    for t in tickers:
        try:
            prices[t] = _last_close(t)
        except Exception:
            log.exception("Harry Browne: prezzo non disponibile per %s.", t)
            missing.append(t)

    # Se manca anche un solo prezzo si rinuncia per oggi, invece di
    # ribilanciare a meta': con tre ETF su quattro portati al 25% e il
    # quarto fermo, il portafoglio andrebbe comunque sistemato domani, cioe'
    # si pagherebbero due giri di operazioni per un solo ribilanciamento.
    # Non segnando la data, il ciclo di domani riprova da solo.
    if missing:
        log.error(
            "Harry Browne: ribilanciamento rimandato, prezzi mancanti per %s. Si riprova al prossimo ciclo.",
            ", ".join(missing),
        )
        notify.alert(
            f"Harry Browne: ribilanciamento rimandato (prezzi mancanti per {', '.join(missing)})",
            level="warning",
        )
        return

    current = {}
    for t in tickers:
        pos = broker.get_open_position(t)
        current[t] = pos["qty"] if pos else 0.0

    orders = harry_browne.rebalance_orders(current, prices, config.LONG_TERM_CAPITAL)
    cash_available = broker.get_cash()
    failed = False
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
            failed = True

    # Come per Advanced: segnare il ribilanciamento come fatto nonostante un
    # errore lascerebbe il portafoglio sbilanciato per un TRIMESTRE intero.
    # Riprovare e' sicuro: gli ordini sono ricalcolati come differenza dalle
    # quote realmente possedute, quindi cio' che e' gia' a target da 0.
    if execute and not failed:
        position_state.set_meta("harry_browne_last_rebalance", today.isoformat())
        notify.alert(f"Lungo termine (Harry Browne): ribilanciamento eseguito il {today.isoformat()}")
    elif failed:
        log.warning("Harry Browne: ribilanciamento NON segnato come completato (errori sopra), si riprova al prossimo ciclo.")


def run_long_term_cycle(
    broker: Broker, execute: bool, today: date | None = None, forza: bool = False
) -> None:
    """`forza` salta il controllo "e' gia' ora?" e ribilancia adesso.

    Serve quando il capitale di lungo termine cambia: il portafoglio resta
    fermo sulle quote vecchie fino alla scadenza successiva (tre mesi per
    Harry Browne, il mese dopo per Advanced), cioe' la differenza resta in
    liquidita' per settimane. Non e' automatico apposta: il ribilanciamento
    a data fissa e' una regola del corso, e saltarla dev'essere una scelta
    esplicita di chi lo lancia, non del programma."""
    today = today or market_today()
    strategy = config.LONG_TERM_AUTO_STRATEGY
    if strategy == "advanced":
        _advanced_monthly_cycle(broker, execute, today, forza=forza)
    elif strategy == "harry_browne":
        _harry_browne_rebalance_cycle(broker, execute, today, forza=forza)
    else:
        log.info("LONG_TERM_AUTO_STRATEGY=none: lungo termine solo a mano, niente da fare.")


def cmd_long_term_once(args: argparse.Namespace) -> None:
    broker = Broker()
    today = market_today()
    if args.execute and not broker.is_trading_day(today):
        log.info("Oggi la borsa USA e' chiusa (weekend o festivo), salto il ciclo di lungo termine.")
        return
    # getattr e non args.forza: lo scheduler notturno costruisce il
    # Namespace a mano (senza le opzioni della riga di comando), e
    # pretendere l'attributo faceva fallire il ciclo automatico.
    run_long_term_cycle(
        broker, execute=args.execute, today=today, forza=getattr(args, "forza", False)
    )
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


def _short_term_positions_value(broker: Broker) -> float:
    return sum(
        abs(p["qty"]) * (p["current_price"] or p["avg_entry_price"])
        for p in _short_term_positions(broker)
    )


def _short_term_equity(broker: Broker) -> float:
    """Capitale su cui si calcola il rischio dell'1% per operazione.

    Equity del conto meno il controvalore degli ETF di lungo termine (che
    hanno il loro capitale dedicato), e comunque non oltre
    SHORT_TERM_CAPITAL: e' la quota del conto che si vuole destinare al
    breve termine, esattamente come LONG_TERM_CAPITAL fa per l'altra
    strategia. Serve quando il conto contiene piu' denaro di quanto si
    voglia far muovere al bot -- il caso tipico di un conto paper Alpaca da
    100.000$ usato per provare una strategia da 10.000. 0 = usa tutto."""
    equity = broker.get_equity()
    long_term_value = sum(
        abs(p["qty"]) * (p["current_price"] or p["avg_entry_price"])
        for p in broker.list_open_positions()
        if p["symbol"] in LONG_TERM_TICKERS
    )
    available = max(0.0, equity - long_term_value)
    if config.SHORT_TERM_CAPITAL > 0:
        return min(available, config.SHORT_TERM_CAPITAL)
    return available


def _short_term_cash(broker: Broker) -> float:
    """Cassa spendibile in nuove posizioni di breve termine. Oltre alla
    cassa vera del conto (nessuna leva), rispetta il tetto
    SHORT_TERM_CAPITAL al netto di quanto e' gia' investito nel breve
    termine: senza questo, dodici posizioni dimensionate sull'1% di 10.000
    potrebbero comunque impegnare molto piu' di 10.000 di controvalore.
    Nel backtest il limite era implicito -- la cassa simulata ERA il
    capitale della strategia."""
    cash = broker.get_cash()
    if config.SHORT_TERM_CAPITAL > 0:
        cash = min(cash, config.SHORT_TERM_CAPITAL - _short_term_positions_value(broker))
    return max(0.0, cash - _pending_entries_value())


def _sector_counts(symbols) -> dict[str, int]:
    """Quante posizioni/ordini per settore. I titoli di cui non si conosce
    il settore non vengono contati: meglio non limitare che limitare in
    base a un dato che non c'e'."""
    counts: dict[str, int] = {}
    for symbol in symbols:
        try:
            etf = sector.get_sector_etf(symbol)
        except Exception:
            log.warning("Settore non determinato per %s, escluso dal conteggio di concentrazione.", symbol)
            continue
        if etf:
            counts[etf] = counts.get(etf, 0) + 1
    return counts


def _sector_is_full(sector_etf: str | None, counts: dict[str, int]) -> bool:
    """Vero se quel settore ha gia' il massimo di posizioni consentito.

    Il tetto di rischio aggregato conta le posizioni, non la loro
    parentela: dodici posizioni tutte nello stesso settore non sono dodici
    scommesse diverse, sono una scommessa moltiplicata per dodici, e
    perdono insieme nello stesso giorno. E' quello che rende profondi i
    drawdown. Misurato su 26 anni e su due universi diversi (STRATEGY.md):
    con il limite il rendimento sale E il drawdown scende.

    Settore sconosciuto = nessun limite: non si blocca un'operazione per un
    dato mancante."""
    if config.SHORT_TERM_MAX_PER_SECTOR <= 0 or not sector_etf:
        return False
    return counts.get(sector_etf, 0) >= config.SHORT_TERM_MAX_PER_SECTOR


def _pending_symbols() -> list[str]:
    return [s for s in position_state.tracked_symbols() if position_state.get(s).get("stage") == "pending"]


def _pending_entries_value() -> float:
    """Cassa gia' impegnata dagli ordini d'ingresso ancora in attesa.

    Un buy stop non tocca la cassa del conto finche' non viene eseguito:
    Alpaca continua a riportare il saldo intero. Senza sottrarla, ogni
    ciclo ripartirebbe dal saldo pieno ignorando gli ordini dei giorni
    precedenti, e il bot potrebbe impegnare piu' cassa di quella che ha --
    la garanzia "nessuna leva" varrebbe solo dentro il singolo ciclo. I
    riempimenti in eccesso verrebbero poi rifiutati dal broker."""
    total = 0.0
    for symbol in _pending_symbols():
        state = position_state.get(symbol)
        total += float(state.get("entry", 0.0) or 0.0) * int(state.get("original_qty", 0) or 0)
    return total


def cmd_short_term_screen(args: argparse.Namespace) -> None:
    broker = Broker() if args.execute else None
    candidates = screen_universe(broker=broker)
    if not candidates:
        print("Nessun candidato trovato.")
        return
    for c in candidates:
        _print_candidate(c)


SECOND_SCALE_OUT_R = 3.0  # STRATEGY.md 2.4 punto 2: "valutare la chiusura intorno a 3R/4R"
SECOND_SCALE_OUT_FRACTION = 0.30  # frazione della size ORIGINALE venduta a 3R
RUNNER_FRACTION = 0.20  # quota residua lasciata correre fino al segnale di inversione
LONG_TERM_MA_PERIOD = 200  # SMA lunga per l'uscita del "runner" (il corso cita "tipo 100/200")

# Trailing stop (STRATEGY.md "Trailing stop: misurato e adottato").
# Dopo 1R lo stop andava a pareggio e restava li' finche' il prezzo non
# chiudeva sotto la SMA200: fra il massimo e quell'incrocio il guadagno
# maturato si restituiva tutto. Ora lo stop sale col massimo raggiunto.
# "Chandelier exit" (Chuck LeBeau): massimo - 3 x ATR(22).
TRAIL_ATR_MULT = config.SHORT_TERM_TRAILING_ATR_MULT
TRAIL_ATR_PERIOD = config.SHORT_TERM_TRAILING_ATR_PERIOD
# Soglia minima di movimento. Nel backtest lo stop e' un numero che si
# aggiorna gratis; qui ogni spostamento e' una cancellazione seguita da un
# reinvio, e fra le due la posizione e' scoperta. Si sposta solo quando la
# protezione guadagnata vale il viaggio. Misurata, non assunta.
TRAIL_MIN_MOVE_ATR = config.SHORT_TERM_TRAILING_MIN_MOVE_ATR


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


def _has_open_limit(open_orders) -> bool:
    """Vero se tra gli ordini aperti c'e' un limit, cioe' la gamba di presa
    di profitto. Guarda anche le gambe degli ordini composti: un OCO al
    broker e' un ordine padre con due gambe (limit + stop)."""
    for order in open_orders:
        legs = getattr(order, "legs", None)
        for leg in (order, *(legs if isinstance(legs, (list, tuple)) else ())):
            if order_type_name(leg) == "limit":
                return True
    return False


def _has_protective_stop(open_orders) -> bool:
    """Vero se fra gli ordini aperti c'e' uno stop di protezione, cioe' uno
    stop che NON sia un ordine d'ingresso (quelli sono acquisti)."""
    for order in open_orders:
        legs = getattr(order, "legs", None)
        for leg in (order, *(legs if isinstance(legs, (list, tuple)) else ())):
            side = str(getattr(getattr(leg, "side", None), "value", getattr(leg, "side", ""))).lower()
            if "stop" in order_type_name(leg) and "buy" not in side:
                return True
    return False


def _exit_structure_incomplete(open_orders, expects_limit: bool) -> bool:
    """La struttura di uscita va (ri)emessa se al broker non c'e' NESSUN
    ordine aperto, oppure se manca la gamba di presa di profitto prevista
    da quello stadio.

    Il secondo caso non e' teorico ed e' il motivo per cui questo controllo
    esiste: appena l'ordine d'ingresso OTO viene eseguito, al broker resta
    aperto il suo stop-loss e nient'altro. Guardando solo "nessun ordine
    aperto" il bot lo scambiava per struttura gia' a posto e non piazzava
    mai il limit a 1R -- la posizione poteva solo andare a stop o correre
    all'infinito, cioe' meta' della strategia (vendere meta' a 1R e portare
    lo stop a pareggio) non entrava mai in funzione. Bug trovato in
    esercizio su una posizione reale in paper trading."""
    if not open_orders:
        return True
    return expects_limit and not _has_open_limit(open_orders)


def _fallback_protect(broker, symbol, direction, abs_qty, stop_price) -> None:
    """Ultima rete di sicurezza.

    Ogni struttura di uscita si costruisce cancellando prima gli ordini
    esistenti (su Alpaca un ordine di vendita aperto riserva le azioni, e
    senza cancellarlo il nuovo verrebbe rifiutato). Quella cancellazione
    lascia una finestra: se poi la nuova struttura non parte -- ordine
    rifiutato, rete caduta a meta' -- la posizione resta SCOPERTA fino al
    ciclo del giorno dopo, che e' esattamente cio' che questo bot non deve
    mai permettere.

    Qui si rinuncia alla scala di uscita per oggi (il ciclo successivo la
    rimette) e si garantisce almeno lo stop sull'intera posizione. Se
    fallisce anche questo, l'eccezione sale al chiamante, che notifica."""
    log.error("%s: struttura di uscita non completata, ripiego su uno stop semplice sull'intera posizione.", symbol)
    broker.cancel_open_orders(symbol)
    broker.submit_stop(symbol, abs_qty, stop_price, direction)
    notify.alert(
        f"{symbol}: struttura di uscita non completata, messa solo la protezione "
        f"(stop {stop_price:.2f} su {abs_qty}); la scala di uscita riparte al prossimo ciclo",
        level="error",
    )


def _protective_stop_price(direction: str, wanted: float, current_price: float | None, fallback: float | None) -> float:
    """Il prezzo da usare per uno stop di protezione.

    Uno stop di vendita va SOTTO il prezzo corrente (per un long); sopra,
    il broker lo rifiuta -- e' un ordine che scatterebbe subito. Lo stop a
    pareggio nasce proprio cosi' quando la posizione, dopo aver superato il
    primo obiettivo, e' tornata sotto il prezzo d'ingresso.

    Senza questo controllo la sequenza era: cancella gli ordini esistenti ->
    prova il pareggio -> rifiutato -> ripiego che riprova lo stesso
    pareggio -> rifiutato di nuovo -> la posizione resta SCOPERTA e il
    ciclo dopo ricomincia identico. Un pareggio irrealizzabile va sostituito
    con lo stop di partenza, che protegge davvero."""
    if current_price is None or current_price <= 0:
        return wanted
    protective = wanted < current_price if direction == "long" else wanted > current_price
    if protective:
        return wanted
    if fallback is not None and ((fallback < current_price) if direction == "long" else (fallback > current_price)):
        log.warning(
            "%s: stop a pareggio %.2f non piazzabile (prezzo %.2f), uso lo stop iniziale %.2f.",
            direction.upper(), wanted, current_price, fallback,
        )
        return fallback
    # Ne' il pareggio ne' lo stop iniziale stanno dalla parte giusta del
    # prezzo: il titolo li ha superati entrambi in gap, senza che lo stop
    # potesse eseguire. Non esiste uno stop piazzabile -- si lascia che il
    # rifiuto del broker faccia scattare l'allarme, invece di far finta.
    log.error(
        "Nessuno stop piazzabile: pareggio %.2f e stop iniziale %s sono dalla parte sbagliata "
        "del prezzo %.2f (gap oltre lo stop). Serve una decisione a mano.",
        wanted, "assente" if fallback is None else f"{fallback:.2f}", current_price,
    )
    return wanted


def _trailing_stop_level(bars, direction: str, since: str | None) -> tuple[float, float] | None:
    """(livello di trailing, ATR) dalle barre giornaliere, o None se non
    calcolabile.

    Il massimo si misura dal giorno DOPO l'esecuzione di 1R, non
    dall'entrata: e' quello che e' stato misurato nel backtest, e la
    differenza non e' cosmetica -- partire dall'entrata alzerebbe subito lo
    stop molto di piu'.

    `since` e' la data in cui la posizione e' passata a '1R_done'. Se manca
    (stato scritto da una versione precedente del bot) si usa tutta la
    finestra disponibile, che e' la scelta prudente: un massimo piu' alto
    non puo' che dare uno stop piu' alto, e _protective_stop_price rifiuta
    comunque qualsiasi livello non protettivo."""
    if not TRAIL_ATR_MULT:
        return None
    if bars is None or len(bars) < TRAIL_ATR_PERIOD + 1:
        return None
    finestra = bars
    if since:
        successive = bars[bars.index > pd.Timestamp(since)]
        # L'ATR ha bisogno della sua finestra: si taglia solo il calcolo del
        # massimo, non la serie su cui si misura la volatilita'.
        if len(successive) == 0:
            return None
        finestra = successive
    valore_atr = atr(bars["high"], bars["low"], bars["close"], TRAIL_ATR_PERIOD)
    if not len(valore_atr) or pd.isna(valore_atr.iloc[-1]) or valore_atr.iloc[-1] <= 0:
        return None
    a = float(valore_atr.iloc[-1])
    if direction == "long":
        return float(finestra["high"].max()) - TRAIL_ATR_MULT * a, a
    return float(finestra["low"].min()) + TRAIL_ATR_MULT * a, a


def _trail_improves(direction: str, nuovo: float, attuale: float, valore_atr: float) -> bool:
    """Vero solo se lo spostamento vale la finestra di scopertura che apre.
    Lo stop non torna MAI indietro: e' la garanzia che rende un trailing
    una protezione e non una scommessa."""
    margine = TRAIL_MIN_MOVE_ATR * valore_atr
    if direction == "long":
        return nuovo > attuale + margine
    return nuovo < attuale - margine


def _place_entered_structure(broker, symbol, direction, abs_qty, entry, risk, stop_price, half) -> bool:
    """Stadio 'entered' (corso, video 44 scenario A/B): sulla meta' da
    vendere a T1 un OCO (sell limit a entrata+1R / sell stop allo stop
    iniziale); sull'altra meta' un sell stop allo stop iniziale. Se il
    prezzo tocca T1 la meta' viene venduta dal limit (come nel backtest,
    che riempie a 1R quando il massimo di giornata lo tocca); se tocca lo
    stop, entrambi gli stop chiudono tutto."""
    broker.cancel_open_orders(symbol)
    oco_qty = min(half, abs_qty)
    rest = abs_qty - oco_qty
    try:
        if oco_qty > 0:
            broker.submit_oco_exit(symbol, oco_qty, direction, _target(entry, risk, 1.0, direction), stop_price)
        if rest > 0:
            broker.submit_stop(symbol, rest, stop_price, direction)
    except Exception:
        _fallback_protect(broker, symbol, direction, abs_qty, stop_price)
        return False
    return True


def _place_1r_done_structure(broker, symbol, direction, abs_qty, entry, risk, second, current_price=None, initial_stop=None, wanted_stop=None) -> bool:
    """Stadio '1R_done': stop a pareggio su tutto il residuo; sulla quota
    da vendere a 3R un OCO (sell limit a entrata+3R / sell stop a
    pareggio), sul runner un sell stop a pareggio."""
    stop = _protective_stop_price(direction, wanted_stop if wanted_stop is not None else entry, current_price, initial_stop)
    broker.cancel_open_orders(symbol)
    oco_qty = min(second, abs_qty)
    rest = abs_qty - oco_qty
    try:
        if oco_qty > 0:
            broker.submit_oco_exit(symbol, oco_qty, direction, _target(entry, risk, SECOND_SCALE_OUT_R, direction), stop)
        if rest > 0:
            broker.submit_stop(symbol, rest, stop, direction)
    except Exception:
        _fallback_protect(broker, symbol, direction, abs_qty, stop)
        return False
    return True


def _place_runner_structure(broker, symbol, direction, abs_qty, entry, current_price=None, initial_stop=None, wanted_stop=None) -> bool:
    """Stadio '3R_done': solo lo stop a pareggio sul runner; l'uscita e'
    decisa dal ciclo giornaliero sull'inversione della SMA200.

    Come le altre due strutture, la cancellazione che precede l'invio apre
    una finestra in cui la posizione e' senza protezione: se l'invio
    fallisce si ripiega (e si urla) invece di lasciarla scoperta in
    silenzio fino al ciclo del giorno dopo."""
    stop = _protective_stop_price(direction, wanted_stop if wanted_stop is not None else entry, current_price, initial_stop)
    broker.cancel_open_orders(symbol)
    try:
        broker.submit_stop(symbol, abs_qty, stop, direction)
    except Exception:
        _fallback_protect(broker, symbol, direction, abs_qty, stop)
        return False
    return True


def _maybe_trail(broker, symbol, direction, abs_qty, entry, risk, second, current_price,
                 initial_stop, state, stage, bars) -> bool:
    """Alza lo stop se il massimo raggiunto lo consente. Vero se spostato.

    Lo stop di riferimento e' quello gia' applicato (`trail_stop` in stato),
    non il pareggio: altrimenti a ogni ciclo si ripartirebbe da capo e lo
    stop non salirebbe mai davvero.

    Se il reinvio fallisce, lo stato NON viene aggiornato: il ciclo dopo
    ritrova lo stop vecchio e riprova, invece di credere di aver protetto
    a un livello che al broker non esiste."""
    livello = _trailing_stop_level(bars, direction, state.get("trail_since"))
    if livello is None:
        return False
    nuovo, valore_atr = livello
    attuale = float(state.get("trail_stop") or entry)
    if not _trail_improves(direction, nuovo, attuale, valore_atr):
        return False
    # Uno stop non protettivo (gia' oltre il prezzo corrente) verrebbe
    # rifiutato dal broker e chiuderebbe subito la posizione al mercato:
    # _protective_stop_price lo intercetta, ma e' meglio non arrivarci.
    if current_price is not None:
        if (direction == "long" and nuovo >= current_price) or (direction == "short" and nuovo <= current_price):
            return False
    if stage == "1R_done":
        riuscito = _place_1r_done_structure(broker, symbol, direction, abs_qty, entry, risk, second,
                                            current_price, initial_stop, wanted_stop=nuovo)
    else:
        riuscito = _place_runner_structure(broker, symbol, direction, abs_qty, entry,
                                           current_price, initial_stop, wanted_stop=nuovo)
    if not riuscito:
        # Il ripiego ha rimesso una protezione, ma NON a questo livello.
        # Registrarlo direbbe una bugia allo stato, e il ciclo di domani
        # non riproverebbe credendo di essere gia' protetto piu' in alto.
        log.warning("%s: il broker ha rifiutato lo stop a %.2f, si riprova al prossimo ciclo.", symbol, nuovo)
        return False
    position_state.set_fields(symbol, trail_stop=nuovo)
    log.info("%s: stop alzato a %.2f (massimo - %.1f x ATR%d).", symbol, nuovo, TRAIL_ATR_MULT, TRAIL_ATR_PERIOD)
    return True


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
    (scaduto, cancellato, riemissione fallita) O se manca la gamba di presa
    di profitto prevista da quello stadio, la struttura viene riemessa
    (auto-riparazione, vedi _exit_structure_incomplete). Il broker non conserva size originale, rischio per
    azione e stadio: li traccia common/position_state.py. Ogni posizione e'
    isolata in un try/except."""
    open_positions = _short_term_positions(broker)
    open_symbols = {pos["symbol"] for pos in open_positions}
    # L'uscita del runner si decide sulla CHIUSURA rispetto alla SMA200: a
    # mercato aperto l'ultima barra giornaliera e' quella di oggi, ancora in
    # formazione, e un affondo intraday chiuderebbe il runner in anticipo su
    # un livello che a fine giornata potrebbe non essere mai stato rotto.
    # Rimandare non lascia nulla di scoperto: lo stop a pareggio e' un
    # ordine depositato al broker.
    bars_are_final = not broker.is_market_open()

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
                #
                # Ma "senza memoria" e "senza protezione" sono due cose
                # diverse, e prima erano lo stesso avviso sommesso. Se al
                # broker non c'e' nemmeno uno stop, quella posizione e'
                # SCOPERTA: e' la situazione peggiore in cui questo bot
                # possa trovarsi, e va gridata. Trovato con la simulazione
                # a guasti iniettati (vedi STRATEGY.md).
                if _has_protective_stop(broker.list_open_orders(symbol)):
                    log.warning("Nessuno stato di rischio salvato per %s, gestione a scaglioni saltata (va seguita a mano). Lo stop al broker c'e'.", symbol)
                else:
                    log.error("%s: posizione di %s azioni SENZA STOP e senza stato salvato. Va protetta a mano, subito.", symbol, abs_qty)
                    notify.alert(
                        f"{symbol}: posizione SCOPERTA ({abs_qty} azioni), nessuno stop al broker e nessun livello salvato. Intervenire a mano.",
                        level="error",
                    )
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
                    _place_1r_done_structure(broker, symbol, direction, abs_qty, entry_price, risk, second, current_price, stop_price)
                    position_state.set_fields(symbol, stage="1R_done", trail_since=str(market_today()))
                    notify.alert(f"{symbol}: 1R raggiunto, venduta meta' posizione, stop a pareggio sul resto")
                elif half == 0 and current_price is not None and _r_multiple(current_price, entry_price, risk, direction) >= 1.0:
                    # Size 1: niente da vendere a meta'; lo stop va comunque
                    # al pareggio (unico modo di applicare "zero rischio dopo 1R").
                    _place_runner_structure(broker, symbol, direction, abs_qty, entry_price, current_price, stop_price)
                    position_state.set_fields(symbol, stage="1R_done", trail_since=str(market_today()))
                elif _exit_structure_incomplete(open_orders, expects_limit=half > 0):
                    if not stop_price:
                        log.error("%s: nessun ordine di uscita e nessuno stop salvato -- VA MESSO A MANO.", symbol)
                        notify.alert(f"{symbol}: posizione SENZA stop e senza livello salvato, intervenire a mano", level="error")
                        continue
                    _place_entered_structure(broker, symbol, direction, abs_qty, entry_price, risk, stop_price, half)
                    t1 = _target(entry_price, risk, 1.0, direction)
                    if open_orders:
                        # Caso normale al primo ciclo dopo l'esecuzione
                        # dell'ingresso: c'era il solo stop-loss dell'OTO.
                        log.info("%s: uscita armata -- %d azioni in vendita a %.2f (1R), stop %.2f su tutto.", symbol, min(half, abs_qty), t1, stop_price)
                        notify.alert(f"{symbol}: uscita armata, meta' in vendita a {t1:.2f}")
                    else:
                        log.warning("%s: ordini di uscita mancanti, riemessi (stop %.2f, T1 %.2f).", symbol, stop_price, t1)
                        notify.alert(f"{symbol}: ordini di uscita mancanti, riemessi", level="warning")

            elif stage == "1R_done":
                if second > 0 and abs_qty <= runner:
                    _place_runner_structure(broker, symbol, direction, abs_qty, entry_price, current_price, stop_price)
                    position_state.set_fields(symbol, stage="3R_done")
                    notify.alert(f"{symbol}: 3R raggiunto, venduta seconda quota, runner in corsa")
                elif _exit_structure_incomplete(open_orders, expects_limit=second > 0):
                    _place_1r_done_structure(broker, symbol, direction, abs_qty, entry_price, risk, second, current_price, stop_price)
                    notify.alert(f"{symbol}: ordini di uscita mancanti, riemessi", level="warning")
                elif bars_are_final:
                    # Solo a mercato chiuso: il massimo di una giornata in
                    # corso non e' ancora il massimo della giornata, e uno
                    # stop alzato su un massimo provvisorio non si puo'
                    # abbassare quando il titolo scende nel pomeriggio.
                    _maybe_trail(broker, symbol, direction, abs_qty, entry_price, risk, second,
                                 current_price, stop_price, state, "1R_done",
                                 get_daily_bars(symbol, period="1y"))

            elif stage == "3R_done":
                reversed_trend = False
                bars = None
                if bars_are_final:
                    # Due anni di barre per una media a 200: con un solo
                    # anno (~252 barre) bastava un buco nei dati perche' la
                    # media non esistesse, e "media non calcolabile" qui
                    # significa "il runner non esce mai" -- in silenzio.
                    bars = get_daily_bars(symbol, period="2y")
                    long_ma = sma(bars["close"], LONG_TERM_MA_PERIOD)
                    if len(long_ma) and not pd.isna(long_ma.iloc[-1]):
                        last_close = float(bars["close"].iloc[-1])
                        reversed_trend = last_close < long_ma.iloc[-1] if direction == "long" else last_close > long_ma.iloc[-1]
                    else:
                        log.warning(
                            "%s: SMA%d non calcolabile (%d barre), uscita del runner rimandata; "
                            "lo stop a pareggio resta al broker.", symbol, LONG_TERM_MA_PERIOD, len(bars),
                        )
                if reversed_trend:
                    try:
                        broker.flatten(symbol)
                    except Exception:
                        # flatten cancella gli stop PRIMA di chiudere: se la
                        # chiusura fallisce la posizione resta aperta e
                        # scoperta. Si rimette la protezione e si lascia lo
                        # stato intatto, cosi' il ciclo dopo riprova.
                        _fallback_protect(
                            broker, symbol, direction, abs_qty,
                            _protective_stop_price(direction, entry_price, current_price, stop_price),
                        )
                        raise
                    position_state.clear(symbol)
                    notify.alert(f"{symbol}: runner chiuso per inversione sulla SMA{LONG_TERM_MA_PERIOD}")
                elif _exit_structure_incomplete(open_orders, expects_limit=False):
                    _place_runner_structure(broker, symbol, direction, abs_qty, entry_price, current_price, stop_price)
                    notify.alert(f"{symbol}: stop del runner mancante, riemesso", level="warning")
                elif bars_are_final and bars is not None:
                    _maybe_trail(broker, symbol, direction, abs_qty, entry_price, risk, second,
                                 current_price, stop_price, state, "3R_done", bars)
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
            expired = bool(since) and (today - date.fromisoformat(str(since))).days > config.SHORT_TERM_PENDING_MAX_DAYS
            order_alive = len(broker.list_open_orders(symbol)) > 0
            if symbol not in candidate_symbols or expired or not order_alive:
                reason = "setup non piu' valido" if symbol not in candidate_symbols else ("scaduto" if expired else "ordine non piu' aperto")
                broker.cancel_open_orders(symbol)
                position_state.clear(symbol)
                log.info("Ingresso pendente su %s cancellato: %s.", symbol, reason)
        except Exception:
            log.exception("Errore riconciliando l'ingresso pendente su %s.", symbol)


EQUITY_HISTORY_DAYS = 252  # ~1 anno di borsa: finestra del massimo di riferimento


def _drawdown_brake_active(broker: Broker, today: date | None = None) -> bool:
    """Corso, video 45: drawdown complessivo da tenere entro il 10-15%. Se
    l'equity del conto e' sotto il massimo DELL'ULTIMO ANNO di piu' di
    SHORT_TERM_MAX_DRAWDOWN_PCT, niente nuove entrate finche' non recupera
    (le posizioni aperte continuano a essere gestite normalmente).

    Il massimo e' su finestra mobile, non storico assoluto, e la ragione e'
    un bug trovato nel backtest: con il massimo assoluto il freno e' una
    trappola senza uscita -- il bot smette di aprire posizioni, quindi
    l'equity non puo' piu' risalire, quindi il massimo resta irraggiungibile
    e il freno non si sblocca MAI. Nel backtest v8b il bot si spegneva nel
    2020 e non operava piu' fino al 2026 (vedi STRATEGY.md "v8b"). Con la
    finestra mobile, dopo al massimo un anno di equity ferma il vecchio
    picco esce dalla finestra e il freno si rilascia da solo."""
    if config.SHORT_TERM_MAX_DRAWDOWN_PCT <= 0:
        return False
    today = today or market_today()
    equity = broker.get_equity()

    history = list(position_state.get_meta("equity_history", []) or [])
    history = [h for h in history if h and h[0] != today.isoformat()]  # un campione al giorno
    history.append([today.isoformat(), equity])
    history = history[-EQUITY_HISTORY_DAYS:]
    position_state.set_meta("equity_history", history)

    peak = max(float(v) for _, v in history)
    drawdown = 1 - equity / peak if peak > 0 else 0.0
    if drawdown >= config.SHORT_TERM_MAX_DRAWDOWN_PCT / 100:
        log.warning(
            "Freno di drawdown attivo: equity %.0f, massimo dell'ultimo anno %.0f (-%.1f%%). Nessuna nuova entrata.",
            equity, peak, drawdown * 100,
        )
        notify.alert(f"Freno di drawdown attivo (-{drawdown * 100:.1f}% dal massimo dell'ultimo anno): nessuna nuova entrata", level="warning")
        return True
    return False


def cmd_short_term_once(args: argparse.Namespace) -> None:
    broker = Broker()
    today = market_today()
    # Il ciclo gira DOPO la chiusura di Wall Street (vedi RUN_TIME): la
    # barra del giorno e' definitiva, come nel backtest e come nel corso
    # ("si analizza la sera, si piazzano gli ordini per il giorno dopo").
    # Gli ordini sono GTC: restano in coda e si attivano alla riapertura.
    # Quindi la condizione giusta non e' "il mercato e' aperto adesso" ma
    # "oggi c'e' stata una seduta".
    if not broker.is_trading_day(today):
        log.info("Oggi la borsa USA e' chiusa (weekend o festivo), salto il ciclo.")
        return

    # La gestione delle posizioni aperte INVIA ordini veri (arma le uscite,
    # riemette stop mancanti): senza --execute il comando deve limitarsi al
    # report, come promesso nella docstring in cima al file. Il ciclo
    # automatico passa sempre execute=True, quindi in esercizio non cambia
    # nulla -- cambia che un'anteprima resta davvero un'anteprima.
    if args.execute:
        manage_open_short_term_positions(broker)
    else:
        log.info("Modalita' report: gestione delle posizioni aperte saltata (invierebbe ordini veri).")

    # Screening e riconciliazione dei pendenti SOLO a mercato chiuso.
    # common/data.py prende le barre giornaliere da yfinance: a mercato
    # aperto l'ultima barra e' quella di OGGI, ancora in formazione --
    # massimo, minimo e chiusura cambiano di minuto in minuto. Analizzarla
    # vuol dire (a) valutare pattern e livelli su un dato che non e' ancora
    # un dato, cosa che il backtest non ha mai testato, e soprattutto (b)
    # cancellare gli ordini in attesa perche' "il setup non c'e' piu'",
    # quando e' solo cambiato il prezzo negli ultimi minuti.
    # Successo davvero: due avvii manuali a 10 minuti di distanza durante
    # la seduta hanno dato liste di candidati completamente diverse e
    # cancellato tutti e 10 gli ordini in attesa piazzati dal primo.
    # La gestione delle posizioni aperte qui sopra resta invece sempre
    # valida: lavora sulle quantita' realmente eseguite, non sulle barre.
    if broker.is_market_open():
        log.info(
            "Mercato ancora aperto: posizioni gestite, screening rimandato alla "
            "chiusura (la barra di oggi non e' definitiva). Il ciclo automatico "
            "delle %s (New York) la trovera' completa.", config.RUN_TIME,
        )
        return

    equity = _short_term_equity(broker)
    candidates = screen_universe(capital=equity, broker=broker)

    if args.execute:
        # Cancella ordini veri al broker: anche questa non e' un'anteprima.
        reconcile_pending_entries(broker, {c.symbol for c in candidates if c.is_actionable}, today)

    # Dopo la riconciliazione: i pendenti cancellati hanno liberato posti.
    #
    # Gli ordini d'ingresso in attesa si contano chiedendoli al BROKER, non
    # leggendoli dal file di stato: il file puo' perdersi (cancellato,
    # disco pieno, cartella spostata) e in quel caso il bot dimenticava di
    # avere ordini aperti, sforando il tetto di posizioni e piazzando un
    # secondo ordine d'ingresso sugli stessi titoli. Trovato con la
    # simulazione a guasti iniettati (vedi STRATEGY.md).
    position_symbols = {p["symbol"] for p in _short_term_positions(broker)}
    entry_symbols = set(broker.open_entry_symbols()) - position_symbols - LONG_TERM_TICKERS
    open_positions_count = len(position_symbols) + len(entry_symbols)
    # Titoli su cui NON si apre un ingresso di breve termine: quelli su cui
    # c'e' gia' una posizione (di qualunque strategia) e gli ETF dei
    # portafogli di lungo termine. Con l'universo full-market lo screening
    # vede anche gli ETF, quindi VTI o GLD possono uscire come candidati
    # mentre il lungo termine li tiene in portafoglio: comprarli di nuovo
    # qui significherebbe raddoppiare quella posizione e gestirla con due
    # logiche diverse.
    off_limits = {p["symbol"] for p in broker.list_open_positions()} | LONG_TERM_TICKERS

    # Quante posizioni ci sono gia' per settore, contando anche gli ordini
    # d'ingresso ancora in attesa (se scattano diventano posizioni, quindi
    # concentrano esattamente allo stesso modo). Il settore si legge dalla
    # cache su disco, quindi costa quasi nulla anche per una dozzina di
    # titoli.
    sector_counts = _sector_counts(position_symbols | entry_symbols)

    if _drawdown_brake_active(broker, today):
        return

    # Nessuna leva: la size e' limitata alla cassa davvero disponibile
    # (decrementata man mano nel ciclo), come nel backtest storico. Il
    # conto paper Alpaca ha margine di default e accetterebbe ordini oltre
    # la cassa -- non e' il profilo di rischio scelto (STRATEGY.md).
    cash_available = _short_term_cash(broker)

    for c in candidates:
        if not c.is_actionable:
            continue
        if c.symbol in off_limits:
            continue  # gia' in posizione, o ETF del lungo termine

        existing = position_state.get(c.symbol)
        # "Sto sostituendo" vale anche quando l'ordine esiste al broker ma
        # lo stato locale non lo sa: cancellare-e-rimpiazzare e' sempre
        # meglio che affiancare un secondo ordine allo stesso titolo.
        replacing = existing.get("stage") == "pending" or c.symbol in entry_symbols
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
        elif _sector_is_full(c.sector_etf, sector_counts):
            # Si salta QUESTO titolo e si continua con gli altri: un
            # settore pieno non dice niente sui candidati degli altri
            # settori, che anzi sono proprio quelli che servono.
            log.info(
                "%s: settore %s gia' al massimo di %d posizioni, salto (concentrazione).",
                c.symbol, c.sector_etf, config.SHORT_TERM_MAX_PER_SECTOR,
            )
            continue

        # Sostituire un pendente libera la cassa che quell'ordine
        # impegnava (gia' sottratta dal saldo iniziale in
        # _short_term_cash): torna disponibile per il nuovo ordine sullo
        # stesso titolo, altrimenti un semplice aggiornamento di livelli
        # sembrerebbe una spesa aggiuntiva e ridurrebbe la size a vuoto.
        freed = 0.0
        if replacing:
            freed = float(existing.get("entry", 0.0) or 0.0) * int(existing.get("original_qty", 0) or 0)

        qty = c.qty
        if c.levels.entry > 0:
            qty = min(qty, math.floor((cash_available + freed) / c.levels.entry))
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
                # Il broker registra le compravendite, non il perche': il
                # pattern e gli avvisi esistono solo adesso e non si
                # ricostruiscono dopo. Senza questa riga, "le operazioni
                # aperte nonostante gli avvisi rendono meno?" resta senza
                # risposta per sempre.
                diario.annota(
                    symbol=c.symbol,
                    direction=c.direction,
                    pattern=c.pattern,
                    trend_score=c.trend.score,
                    entry=round(c.levels.entry, 4),
                    stop=round(c.levels.stop_loss, 4),
                    risk_per_share=round(c.levels.risk_per_share, 4),
                    qty=qty,
                    settore=c.sector_etf,
                    settore_conferma=c.sector_passes,
                    avvisi=list(c.notes),
                )
            except APIError as exc:
                # Rifiuto del broker: e' una risposta, non un guasto del bot.
                # Va loggato per esteso ma in una riga, senza traceback: un
                # muro di stack trace per un caso previsto nasconde gli
                # errori veri (stessa logica del rumore nei log).
                log.error("Ordine per %s rifiutato dal broker: %s", c.symbol, exc)
                notify.alert(f"Ordine per {c.symbol} rifiutato dal broker: {exc}", level="error")
                opened = False
            except Exception:
                log.exception("Errore inviando l'ordine per %s, salto al prossimo candidato.", c.symbol)
                notify.alert(f"Errore inviando l'ordine per {c.symbol}", level="error")
                opened = False

        # Si aggiorna anche in modalita' report-only (candidato che
        # verrebbe messo in attesa rispettando il tetto di rischio
        # aggregato, cosi' l'anteprima riflette cosa accadrebbe con
        # --execute) -- ma NON se l'invio ordine e' effettivamente fallito.
        # Il CONTEGGIO delle posizioni non cresce per un pendente
        # sostituito (gia' contato), la CASSA invece cambia comunque: il
        # nuovo ordine impegna una cifra diversa dal vecchio.
        if opened:
            cash_available -= qty * c.levels.entry - freed
            if not replacing:
                open_positions_count += 1
                if c.sector_etf:
                    sector_counts[c.sector_etf] = sector_counts.get(c.sector_etf, 0) + 1
        elif replacing:
            # Il vecchio ordine e' stato cancellato ma il nuovo non e'
            # partito: quella cassa e' di nuovo libera.
            cash_available += freed


def _pnl_pct(current: float, entry: float, direction: str) -> float:
    if entry <= 0:
        return 0.0
    return ((current - entry) / entry * 100) * (1 if direction == "long" else -1)


_STAGE_LABEL = {
    "pending": "ordine in attesa, non ancora eseguito",
    "entered": "aperta, punta al primo obiettivo (1R)",
    "1R_done": "primo obiettivo preso, stop a pareggio: non puo' piu' perdere",
    "3R_done": "secondo obiettivo preso, corre libera",
}


def cmd_rendiconto(args: argparse.Namespace) -> None:
    """Come sta andando DAVVERO: le operazioni gia' chiuse.

    Tutto quello che sappiamo di questa strategia viene da simulazioni sul
    2005-2026. Di quello che il bot ha fatto sul serio non sapevamo niente,
    perche' lo stato locale cancella la posizione appena si chiude. Qui lo
    storico si ricostruisce dagli eseguiti conservati dal broker, quindi
    copre anche le operazioni chiuse prima che questo comando esistesse.
    """
    broker = Broker()
    fills = broker.list_filled_orders()
    operazioni = rendiconto.ricostruisci(fills, escludi=LONG_TERM_TICKERS)
    rendiconto.abbina(operazioni, diario.leggi())
    s = rendiconto.statistiche(operazioni)

    print("\n" + "=" * 62)
    print(" RENDICONTO OPERAZIONI CHIUSE (solo azioni, breve termine)")
    print("=" * 62)

    if not s["totale"]:
        print("\n  Nessuna operazione ancora chiusa.")
        print("  Il rendiconto conta solo i giri completi (comprato E rivenduto):")
        print("  le posizioni ancora aperte non hanno un risultato, e metterle")
        print("  qui dentro falserebbe le medie. Guardale con 'status'.\n")
        return

    perc = s["percentuale_successo"]
    pf = s["profit_factor"]
    print(f"\n  Operazioni chiuse   : {s['totale']}")
    print(f"  Vinte / perse       : {s['vinte']} / {s['perse']}   ({perc:.0f}% di successo)")
    print(f"  Risultato totale    : {s['pnl_totale']:+,.2f} USD")
    print(f"  Guadagno medio      : {s['guadagno_medio']:+,.2f} USD")
    print(f"  Perdita media       : {s['perdita_media']:+,.2f} USD")
    print(f"  Profit factor       : {pf:.2f}"
          + ("   (sotto 1 = si perde)" if pf < 1 else "   (sopra 1,5 = margine reale)" if pf >= 1.5 else ""))
    if s["erre_medio"] is not None:
        print(f"  Risultato medio in R: {s['erre_medio']:+.2f}R   (su {s['con_erre']} operazioni su {s['totale']})")
    print(f"  Durata media        : {s['giorni_medi']:.0f} giorni")

    if s["totale"] < 100:
        print(f"\n  ATTENZIONE: {s['totale']} operazioni sono POCHE. Con questi numeri")
        print("  una striscia di sfortuna e una strategia rotta si somigliano.")
        print("  Servono alcune centinaia di operazioni prima di cambiare qualcosa")
        print("  sulla base di questo rendiconto.")

    pattern = rendiconto.per_pattern(operazioni)
    if pattern:
        print("\n" + "-" * 62)
        print(" PER PATTERN")
        print("-" * 62)
        print(f"  {'pattern':<26s} {'n':>4s} {'successo':>9s} {'risultato':>12s} {'PF':>6s}")
        for nome, r in sorted(pattern.items(), key=lambda kv: -kv[1]["pnl"]):
            pf = "inf" if r["profit_factor"] == float("inf") else f"{r['profit_factor']:.2f}"
            print(f"  {nome:<26s} {r['totale']:>4d} {r['successo']:>8.0f}% {r['pnl']:>+11,.2f} {pf:>6s}")

    avvisi = rendiconto.per_numero_avvisi(operazioni)
    if avvisi:
        print("\n" + "-" * 62)
        print(" PER NUMERO DI AVVISI (settore, resistenza, divergenza)")
        print("-" * 62)
        print(f"  {'avvisi':<26s} {'n':>4s} {'successo':>9s} {'risultato':>12s} {'PF':>6s}")
        for n, r in sorted(avvisi.items()):
            etichetta = ("nessun avviso" if n == 0 else
                         "1 avviso" if n == 1 else
                         f"{n} avvisi" if n < 3 else "3 o piu' avvisi")
            pf = "inf" if r["profit_factor"] == float("inf") else f"{r['profit_factor']:.2f}"
            print(f"  {etichetta:<26s} {r['totale']:>4d} {r['successo']:>8.0f}% {r['pnl']:>+11,.2f} {pf:>6s}")

    senza_diario = sum(1 for o in operazioni if o.pattern is None)
    if senza_diario:
        quante = (f"{senza_diario} operazione e' precedente" if senza_diario == 1
                  else f"{senza_diario} operazioni sono precedenti")
        print(f"\n  ({quante} al diario di bordo: di quelle")
        print("   non si sa il pattern, e restano fuori dalle due tabelle qui sopra.)")

    recenti = operazioni[-args.ultime:] if args.ultime else operazioni
    print("\n" + "-" * 62)
    print(f" ULTIME {len(recenti)} OPERAZIONI")
    print("-" * 62)
    print(f"  {'titolo':<7s} {'chiusa':<11s} {'gg':>3s} {'risultato':>11s} {'R':>7s}  pattern")
    for o in recenti:
        erre = f"{o.erre:+.2f}" if o.erre is not None else "  n/d"
        etichetta = o.pattern or "-"
        if o.avvisi:
            quanti = len(o.avvisi)
            etichetta += f"  ({quanti} avviso)" if quanti == 1 else f"  ({quanti} avvisi)"
        print(f"  {o.symbol:<7s} {o.chiusura.date().isoformat():<11s} {o.giorni:>3d}"
              f" {o.pnl:>+10,.2f} {erre:>7s}  {etichetta}")
    print()


def cmd_chiudi(args: argparse.Namespace) -> None:
    """Chiude a mercato una posizione APERTA di breve termine.

    Le azioni sono trattenute dallo stop-loss: finche' quell'ordine esiste,
    una vendita viene rifiutata per "insufficient qty". Quindi l'ordine e'
    obbligato: prima si cancellano gli ordini di protezione, poi si vende.

    E c'e' un istante, fra i due, in cui la posizione e' SCOPERTA. Con il
    mercato aperto dura il tempo di un ordine a mercato. Con il mercato
    chiuso durerebbe fino all'apertura dopo, perche' l'ordine resta in coda:
    una notte intera senza stop, magari su un titolo che apre in gap. Per
    questo a mercato chiuso il comando si rifiuta invece di "provarci".
    """
    symbol = args.symbol.upper()
    broker = Broker()

    posizione = broker.get_open_position(symbol)
    if posizione is None:
        print(f"\n  Su {symbol} non c'e' nessuna posizione aperta: niente da chiudere.")
        print("  (per togliere un ordine d'ingresso in attesa usa invece: annulla"
              f" {symbol} --execute)\n")
        return

    qty = float(posizione["qty"])
    verso = "LONG" if qty > 0 else "SHORT"
    prezzo = posizione.get("current_price") or posizione.get("avg_entry_price")
    aperti = broker.list_open_orders(symbol)

    print(f"\n  {symbol}: posizione {verso} di {abs(qty):g} azioni"
          + (f", ora a {float(prezzo):.2f}" if prezzo else ""))
    print(f"  Ordini di protezione da togliere prima di vendere: {len(aperti)}")
    for o in aperti:
        p_ord = getattr(o, "stop_price", None) or getattr(o, "limit_price", None)
        print(f"    - {order_type_name(o)} {getattr(o, 'side', '')} {getattr(o, 'qty', '')}"
              + (f" a {float(p_ord):.2f}" if p_ord else ""))

    if not args.execute:
        print("\n  (prova: non e' stato chiuso niente. Riesegui con --execute per chiudere.)\n")
        return

    if not broker.is_market_open():
        print("\n  RIFIUTATO: il mercato e' chiuso.")
        print("  Per vendere bisogna prima togliere lo stop-loss, e a mercato chiuso")
        print("  l'ordine di vendita resterebbe in coda fino all'apertura: la posizione")
        print("  passerebbe la notte senza protezione.")
        print("  Rilancia questo comando a mercato aperto (15:30-22:00 ora italiana).\n")
        return

    cancellati = broker.cancel_open_orders(symbol)
    intere = int(abs(qty))
    if intere <= 0:
        print(f"\n  {symbol}: {abs(qty):g} azioni, meno di un'azione intera: non e'")
        print("  vendibile a mercato. Annullati comunque gli ordini di protezione.\n")
        position_state.clear(symbol)
        return

    if qty > 0:
        broker.sell_market(symbol, intere)
    else:
        broker.buy_market(symbol, intere)
    position_state.clear(symbol)

    print(f"\n  {symbol}: tolti {cancellati} ordini di protezione e mandata la chiusura")
    print(f"  a mercato di {intere} azioni. Controlla con 'status' fra qualche minuto.\n")
    notify.alert(f"{symbol}: posizione chiusa a mano ({intere} azioni)")


def cmd_annulla(args: argparse.Namespace) -> None:
    """Annulla l'ordine d'INGRESSO ancora in attesa su un titolo.

    La protezione che conta: se la posizione e' GIA' APERTA il comando si
    rifiuta di fare qualsiasi cosa. Cancellare gli ordini di un titolo in
    portafoglio non annullerebbe un ingresso -- toglierebbe lo stop-loss e
    la presa di profitto, lasciando la posizione scoperta. E' esattamente
    il tipo di errore che un comando "annulla" invita a fare di fretta."""
    symbol = args.symbol.upper()
    broker = Broker()

    posizione = broker.get_open_position(symbol)
    if posizione is not None:
        qty = posizione.get("qty")
        print(f"\n  RIFIUTATO: su {symbol} c'e' gia' una posizione APERTA ({qty} azioni).")
        print("  Cancellare gli ordini adesso toglierebbe lo stop-loss e la presa di")
        print("  profitto, lasciando la posizione senza protezione.")
        print(f"  Per uscire davvero dalla posizione serve venderla, non annullare un ordine.\n")
        return

    aperti = broker.list_open_orders(symbol)
    if not aperti:
        print(f"\n  Su {symbol} non c'e' nessun ordine in attesa: niente da annullare.\n")
        position_state.clear(symbol)
        return

    print(f"\n  {symbol}: {len(aperti)} ordine/i in attesa, nessuna posizione aperta.")
    for o in aperti:
        prezzo = getattr(o, "stop_price", None) or getattr(o, "limit_price", None)
        print(f"    - {order_type_name(o)} {getattr(o, 'side', '')} {getattr(o, 'qty', '')}"
              + (f" a {float(prezzo):.2f}" if prezzo else ""))

    if not args.execute:
        print("\n  (prova: non e' stato cancellato niente. Riesegui con --execute per annullare.)\n")
        return

    cancellati = broker.cancel_open_orders(symbol)
    position_state.clear(symbol)
    print(f"\n  Annullati {cancellati} ordini su {symbol}. Il titolo torna libero.\n")
    notify.alert(f"{symbol}: ordine d'ingresso annullato a mano ({cancellati} ordini)")


def cmd_status(args: argparse.Namespace) -> None:
    """Rendiconto leggibile: quanto c'e', come vanno le posizioni, cosa si
    aspetta il bot.

    Esisteva un buco banale ma reale: dopo mesi di lavoro sul motore non
    c'era un modo di chiedere "come sto andando?" senza aprire il sito di
    Alpaca o leggere i log. Questo comando non invia MAI ordini."""
    broker = Broker()
    account = broker.get_account_snapshot()
    cur = account["currency"]
    positions = broker.list_open_positions()

    short_term = [p for p in positions if p["symbol"] not in LONG_TERM_TICKERS]
    long_term = [p for p in positions if p["symbol"] in LONG_TERM_TICKERS]
    investito = sum(abs(p["qty"]) * (p["current_price"] or p["avg_entry_price"]) for p in positions)

    print(f"\n{'='*62}")
    print(f" RENDICONTO  --  {market_now().strftime('%d/%m/%Y %H:%M')} (ora di New York)")
    print(f"{'='*62}")
    print(f"\n  Valore totale del conto : {account['equity']:>12,.2f} {cur}")
    print(f"  di cui investito       : {investito:>12,.2f} {cur}")
    print(f"  liquidita'             : {account['cash']:>12,.2f} {cur}")
    if account["last_equity"] > 0:
        giorno = account["equity"] - account["last_equity"]
        # Il segno sta DENTRO la formattazione (+12,.2f), non incollato
        # prima: incollandolo, l'allineamento a destra lo separava dal
        # numero ("+     200.00").
        print(f"  variazione di oggi     : {giorno:>+12,.2f} {cur}  ({giorno / account['last_equity'] * 100:+.2f}%)")

    # --- breve termine
    print(f"\n{'-'*62}")
    print(f" AZIONI (breve termine) -- {len(short_term)} posizioni aperte")
    print(f"{'-'*62}")
    if not short_term:
        print("  nessuna posizione aperta.")
    for p in sorted(short_term, key=lambda x: x["symbol"]):
        stato = position_state.get(p["symbol"])
        direction = stato.get("direction") or ("long" if p["qty"] > 0 else "short")
        price = p["current_price"] or p["avg_entry_price"]
        pnl = _pnl_pct(price, p["avg_entry_price"], direction)
        guadagno = (price - p["avg_entry_price"]) * p["qty"]
        segno = "+" if guadagno >= 0 else ""
        print(f"\n  {p['symbol']:<6} {int(abs(p['qty'])):>5} azioni a {p['avg_entry_price']:.2f}  ->  ora {price:.2f}")
        print(f"         {segno}{guadagno:,.2f} {cur}  ({segno}{pnl:.1f}%)")
        stadio = stato.get("stage")
        if stadio:
            print(f"         {_STAGE_LABEL.get(stadio, stadio)}")
        if stato.get("pattern"):
            print(f"         entrata per: {stato['pattern']}")

    # --- ordini in attesa
    attesa = sorted(set(broker.open_entry_symbols()) - {p["symbol"] for p in positions} - LONG_TERM_TICKERS)
    print(f"\n{'-'*62}")
    print(f" IN ATTESA -- {len(attesa)} ordini d'ingresso non ancora scattati")
    print(f"{'-'*62}")
    if not attesa:
        print("  nessun ordine in attesa.")
    for symbol in attesa:
        stato = position_state.get(symbol)
        livello = stato.get("entry")
        stop = stato.get("stop_price")
        if livello and stop:
            print(f"  {symbol:<6} compra sopra {float(livello):.2f}, stop a {float(stop):.2f}  ({stato.get('pattern', 'n/d')})")
        else:
            print(f"  {symbol:<6} ordine al broker (livelli non salvati localmente)")

    # --- lungo termine
    print(f"\n{'-'*62}")
    print(f" ETF (lungo termine, {config.LONG_TERM_AUTO_STRATEGY})")
    print(f"{'-'*62}")
    if not long_term:
        print("  nessun ETF in portafoglio.")
    valore_lt = sum(abs(p["qty"]) * (p["current_price"] or p["avg_entry_price"]) for p in long_term)
    for p in sorted(long_term, key=lambda x: x["symbol"]):
        price = p["current_price"] or p["avg_entry_price"]
        valore = abs(p["qty"]) * price
        quota = valore / valore_lt * 100 if valore_lt else 0
        guadagno = (price - p["avg_entry_price"]) * p["qty"]
        segno = "+" if guadagno >= 0 else ""
        print(f"  {p['symbol']:<6} {valore:>10,.2f} {cur}  ({quota:>4.1f}% del portafoglio ETF)   {segno}{guadagno:,.2f}")
    if config.LONG_TERM_AUTO_STRATEGY == "harry_browne":
        ultimo = position_state.get_meta("harry_browne_last_rebalance")
        if ultimo:
            prossimo_dovuto = harry_browne.is_rebalance_due(date.fromisoformat(ultimo), market_today())
            print(f"\n  Obiettivo: 25% ciascuno. Ultimo ribilanciamento: {ultimo}.")
            ogni = {"quarterly": "ogni 3 mesi", "semiannual": "ogni 6 mesi", "annual": "una volta l'anno"}
            cadenza = ogni.get(config.REBALANCE_FREQUENCY, config.REBALANCE_FREQUENCY)
            print(f"  Prossimo: {'DOVUTO ORA' if prossimo_dovuto else f'non ancora ({cadenza})'}.")
        else:
            print("\n  Nessun ribilanciamento ancora registrato.")

    print(f"\n{'='*62}\n")


# Attese (secondi) tra i tentativi quando una fase del ciclo fallisce
# perche' il broker e' irraggiungibile. Caso reale: il bot viene lanciato
# subito dopo l'accensione del PC e la connessione non e' ancora pronta.
# Senza questi tentativi il giro del giorno andrebbe perso del tutto --
# nessuna gestione delle posizioni aperte, nessun nuovo ordine.
CYCLE_RETRY_WAITS = (60, 300, 900)

# I retry di broker.py coprono il singolo scatto di rete (secondi); questi
# coprono l'assenza di connessione vera e propria (minuti).

# Un ciclo alla volta: il giro iniziale all'avvio e quello schedulato sono
# due job distinti, quindi senza questo lucchetto un giro iniziale ancora
# in attesa di rete potrebbe sovrapporsi a quello delle 16:15 e mandare
# ordini doppi.
_cycle_lock = threading.Lock()


# Codici HTTP che dicono "il server ha un problema adesso", non "la tua
# richiesta e' sbagliata": ha senso riprovare fra qualche minuto.
_TRANSIENT_HTTP_STATUSES = (429, 500, 502, 503, 504)


def _is_network_failure(exc: BaseException) -> bool:
    """Vero se l'eccezione (o una delle sue cause) e' un guasto TRANSITORIO
    del broker: irraggiungibile, che non risponde, o che risponde con un
    errore suo.

    Sono gli unici errori per cui ha senso riprovare -- un ordine rifiutato
    o un bug non migliorano aspettando.

    Il caso del server che risponde 500 e' stato aggiunto dopo averlo visto
    accadere: Alpaca ha risposto "500 Internal Server Error" sulla prima
    chiamata del ciclo (il calendario di borsa) e l'intero giro della
    giornata e' stato abbandonato senza un solo tentativo, breve e lungo
    termine insieme. Un errore del loro server non e' un motivo per saltare
    una giornata di gestione delle posizioni.

    Riprovare il ciclo e' sicuro anche dopo un 500 su un invio ordine: il
    ciclo rilegge posizioni e ordini dal broker e riconcilia, invece di
    accodare ordini nuovi (vedi reconcile_pending_entries e
    open_entry_symbols)."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
            return True
        if isinstance(current, requests.exceptions.HTTPError):
            response = getattr(current, "response", None)
            if getattr(response, "status_code", None) in _TRANSIENT_HTTP_STATUSES:
                return True
        if isinstance(current, APIError) and current.status_code in _TRANSIENT_HTTP_STATUSES:
            return True
        current = current.__cause__ or current.__context__
    return False


def _run_step_with_retry(name: str, run) -> None:
    """Esegue una fase del ciclo senza mai propagare eccezioni, riprovando
    se il broker e' irraggiungibile.

    Ripetere e' sicuro: il ciclo e' idempotente per costruzione -- rilegge
    posizioni e ordini pendenti dal broker e riconcilia lo stato invece di
    accodare nuovi ordini (vedi reconcile_pending_entries)."""
    attempts = len(CYCLE_RETRY_WAITS) + 1
    for attempt in range(1, attempts + 1):
        try:
            run()
            return
        except Exception as exc:
            if attempt == attempts or not _is_network_failure(exc):
                log.exception("Ciclo %s fallito.", name)
                notify.alert(f"Ciclo {name} fallito, controlla i log", level="error")
                return
            wait = CYCLE_RETRY_WAITS[attempt - 1]
            log.warning(
                "Ciclo %s: broker irraggiungibile (%s). Riprovo tra %d secondi "
                "(tentativo %d di %d).",
                name, type(exc).__name__, wait, attempt + 1, attempts,
            )
            time.sleep(wait)


def _run_cycle_safely() -> None:
    """Un ciclo schedulato non deve mai propagare un'eccezione: un guasto
    sistemico (broker irraggiungibile, errore imprevisto) va notificato e
    registrato, non deve far morire lo scheduler o saltare i cicli futuri.
    Breve e lungo termine sono isolati l'uno dall'altro."""
    if not _cycle_lock.acquire(blocking=False):
        log.warning("Un ciclo e' gia' in corso: salto questa esecuzione per non duplicare ordini.")
        return
    try:
        _run_step_with_retry("breve termine", lambda: cmd_short_term_once(argparse.Namespace(execute=True)))
        _run_step_with_retry(
            "lungo termine",
            lambda: cmd_long_term_once(argparse.Namespace(execute=True, forza=False)),
        )
    finally:
        _cycle_lock.release()


def cmd_schedule(args: argparse.Namespace) -> None:
    notify.alert("Bot avviato, scheduler attivo")

    hour, minute = (int(x) for x in config.RUN_TIME.split(":"))
    scheduler = BlockingScheduler(timezone=MARKET_TIMEZONE)
    # Il fuso va passato AL TRIGGER, non solo allo scheduler. APScheduler
    # applica il fuso dello scheduler solo ai trigger creati da stringa
    # ("cron"); un CronTrigger costruito come oggetto usa il fuso locale
    # della macchina (BaseScheduler._create_trigger lo restituisce
    # invariato). Su un PC italiano il ciclo partiva quindi alle 16:15
    # ITALIANE, cioe' 45 minuti dopo l'APERTURA di Wall Street invece che
    # 15 minuti dopo la chiusura: ogni giorno l'analisi girava sulla barra
    # del giorno ancora in formazione. Trovato nel log di un PC reale.
    daily_job = scheduler.add_job(
        _run_cycle_safely,
        CronTrigger(day_of_week="mon-fri", hour=hour, minute=minute, timezone=MARKET_TIMEZONE),
        misfire_grace_time=3600,
        coalesce=True,
    )
    # Il giro iniziale e' un job dello scheduler, non una chiamata prima di
    # start(): se la rete non c'e' ancora, i suoi tentativi possono durare
    # minuti, e facendolo prima terrebbero l'appuntamento quotidiano non
    # ancora registrato per tutto quel tempo.
    scheduler.add_job(_run_cycle_safely, misfire_grace_time=None)
    log.info(
        "Scheduler avviato: ciclo breve + lungo termine (%s) ogni giorno feriale alle %s %s "
        "(prossima esecuzione: %s).",
        config.LONG_TERM_AUTO_STRATEGY, config.RUN_TIME, MARKET_TIMEZONE,
        daily_job.trigger.get_next_fire_time(None, market_now()),
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
    p.add_argument("--forza", action="store_true",
                   help="ribilancia adesso anche se la scadenza non e' arrivata (es. dopo aver cambiato LONG_TERM_CAPITAL)")
    p.set_defaults(func=cmd_long_term_once)

    p = sub.add_parser("short-term-screen", help="Report candidati (nessun ordine)")
    p.add_argument("--execute", action="store_true", help="usa le chiavi Alpaca per l'universo full-market (nessun ordine viene comunque inviato)")
    p.set_defaults(func=cmd_short_term_screen)

    p = sub.add_parser("short-term-once", help="Un ciclo: gestione posizioni aperte + screening + (opzionale) ordini")
    p.add_argument("--execute", action="store_true")
    p.set_defaults(func=cmd_short_term_once)

    p = sub.add_parser("status", help="Rendiconto: quanto c'e', come vanno le posizioni, cosa si aspetta il bot")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("annulla", help="Annulla l'ordine d'ingresso in attesa su un titolo (non tocca le posizioni aperte)")
    p.add_argument("symbol", help="Il titolo, es. IBIT")
    p.add_argument("--execute", action="store_true", help="Annulla davvero (senza, mostra solo cosa farebbe)")
    p.set_defaults(func=cmd_annulla)

    p = sub.add_parser("rendiconto", help="Come sta andando davvero: le operazioni gia' chiuse")
    p.add_argument("--ultime", type=int, default=20, help="quante operazioni elencare (0 = tutte)")
    p.set_defaults(func=cmd_rendiconto)

    p = sub.add_parser("chiudi", help="Chiude a mercato una posizione aperta (toglie prima gli ordini di protezione)")
    p.add_argument("symbol", help="Il titolo, es. BITO")
    p.add_argument("--execute", action="store_true", help="Chiude davvero (senza, mostra solo cosa farebbe)")
    p.set_defaults(func=cmd_chiudi)

    p = sub.add_parser("schedule", help="Ciclo breve + lungo termine schedulato ogni giorno feriale")
    p.set_defaults(func=cmd_schedule)

    args = parser.parse_args()
    setup_logging()
    args.func(args)


if __name__ == "__main__":
    main()
