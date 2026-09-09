"""Stress test: il ciclo VERO del bot contro un broker simulato, per
centinaia di giorni, con guasti iniettati.

Non verifica "il codice fa quello che ho scritto" ma "il bot non viola mai
le sue regole", che e' una domanda diversa e piu' utile. Le regole:

  1. ogni posizione aperta dal bot ha stop al broker per l'INTERA quantita'
  2. mai due ordini d'ingresso sullo stesso titolo
  3. mai una posizione e un ordine d'ingresso insieme sullo stesso titolo
  4. mai piu' vendite riservate delle azioni possedute (Alpaca rifiuterebbe)
  5. mai piu' di 12 fra posizioni e ordini in attesa
  6. mai cassa negativa (nessuna leva)
  7. mai silenzio su una posizione scoperta che il bot non ha aperto
  8. una posizione allo stadio "entered"/"1R_done" ha al broker anche la
     gamba di PRESA DI PROFITTO prevista, non solo lo stop
  9. una posizione aperta ieri e' protetta gia' PRIMA del ciclo di oggi

Ha gia' trovato un bug vero: con il file di stato perso il bot piazzava un
SECONDO ordine d'ingresso sui titoli che aveva gia' in attesa, perche'
leggeva i pendenti dalla propria memoria invece che dal broker.

Le regole 8 e 9 sono nate da un test di mutazione su questa stessa suite.
Tre guasti gravi introdotti apposta nel codice NON venivano visti:
  - "non riemettere mai la struttura di uscita mancante": nessuna regola
    guardava la presa di profitto, quindi un bot che sa solo andare a stop
    o correre all'infinito -- meta' della strategia spenta -- passava;
  - "togliere la gamba stop-loss dall'ordine d'ingresso": il controllo
    girava DOPO il ciclo, che nel frattempo aveva rimesso lo stop, quindi
    la notte scoperta fra l'esecuzione e il ciclo successivo non veniva
    mai osservata;
  - "ingoiare i fallimenti di cancellazione": non c'era abbastanza
    campione perche' il caso si presentasse.
Una suite che non vede un guasto introdotto apposta non sta verificando
quel guasto: e' la differenza fra "i test passano" e "i test proteggono"."""
import argparse
import os
import random
import tempfile
from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd

import bot
from common import position_state
from short_term.levels import EntryLevels
from short_term.screener import Candidate
from short_term.trend import TrendQualification
from tests.fake_broker import FakeBroker, Position, Rejected

SYMBOLS = [f"SYM{i}" for i in range(30)]


def _candidate(sym, price, rng):
    risk = round(rng.uniform(1.0, price * 0.10), 2)
    entry = round(price * rng.uniform(1.001, 1.03), 2)
    lv = EntryLevels("long", entry, round(entry - risk, 2), risk)
    return Candidate(
        symbol=sym, direction="long", pattern="Pullback Semplice",
        trend=TrendQualification("long", rng.randint(2, 6), {}), levels=lv,
        qty=max(1, int(100 / risk)), ribbon_aligned=True, sector_etf="XLK",
        sector_passes=True, earnings_warn=False, sr_too_close=False,
        price_blocks_trade=False, has_divergence=False,
        proximity_52w=rng.random(), last_close=price,
    )


def _check(broker, day, violations, foreign, alerts):
    for sym, pos in broker.positions.items():
        if sym in bot.LONG_TERM_TICKERS:
            continue
        stops = sum(o.qty for o in broker.orders
                    if o.symbol == sym and o.side == "sell" and o.type == "stop")
        if stops < pos.qty:
            if sym in foreign:
                # Il bot non puo' proteggere cio' che non ha aperto (non ne
                # conosce lo stop), ma non deve tacere.
                if not any(sym in m for _, m in alerts):
                    violations.append(f"giorno {day}: {sym} scoperta e il bot ha taciuto")
            else:
                violations.append(f"giorno {day}: {sym} ha {pos.qty} azioni ma stop per {stops}")
        if broker._reserved_sell_qty(sym) > pos.qty:
            violations.append(f"giorno {day}: {sym} vendite riservate oltre le azioni possedute")
        # Regola 8: lo stop protegge dalla perdita, ma il limit a 1R e'
        # il modo in cui la strategia incassa. Senza questo controllo un
        # bot che non arma mai la presa di profitto passava la suite.
        state = position_state.get(sym)
        stage = state.get("stage")
        original = int(state.get("original_qty") or 0)
        if stage in ("entered", "1R_done") and original:
            half, second, _ = bot._tranches(original)
            expected = half if stage == "entered" else second
            limits = [o for o in broker.orders
                      if o.symbol == sym and o.side == "sell" and o.type == "limit"]
            # Rinunciare alla presa di profitto per un ciclo e' previsto
            # (_fallback_protect: meglio il solo stop che niente), ma non
            # in silenzio -- e' la stessa regola delle posizioni scoperte.
            # Restare senza presa di profitto per un ciclo e' previsto --
            # _fallback_protect ci rinuncia per garantire almeno lo stop, e
            # un errore isolato su un titolo lo salta fino al giorno dopo --
            # ma sempre dicendolo. Un avviso INFORMATIVO non basta: e' quello
            # che il bot manda anche quando la struttura e' andata a buon
            # fine, e usarlo come esenzione rendeva la regola cieca.
            reported = any(sym in m and level in ("warning", "error") for level, m in alerts)
            if expected > 0 and not limits and not reported:
                violations.append(f"giorno {day}: {sym} stadio {stage} senza presa di profitto al broker")

    for sym in {o.symbol for o in broker.orders}:
        buys = [o for o in broker.orders if o.symbol == sym and o.side == "buy"]
        if len(buys) > 1:
            violations.append(f"giorno {day}: {sym} ha {len(buys)} ordini d'ingresso")
        if buys and sym in broker.positions:
            violations.append(f"giorno {day}: {sym} ha una posizione E un ordine d'ingresso")
    if broker.cash < -0.01:
        violations.append(f"giorno {day}: cassa negativa {broker.cash:.2f}")
    own = len([s for s in broker.positions if s not in foreign])
    if own + len([o for o in broker.orders if o.side == "buy"]) > 12:
        violations.append(f"giorno {day}: oltre il tetto di 12 posizioni")
    if broker.rejections:
        violations.append(f"giorno {day}: rifiuti dal broker {broker.rejections[:2]}")
        broker.rejections.clear()


def _run(seed, days, chaos, tmp_path):
    rng = random.Random(seed)
    broker = FakeBroker(cash=20_000.0)
    prices = {s: rng.uniform(20, 300) for s in SYMBOLS}
    violations, foreign, alerts = [], set(), []
    opened_before: set[str] = set()
    position_state.STATE_PATH = str(tmp_path / f"positions-{seed}.json")
    falling = pd.DataFrame({"close": [500.0] * 250 + [1.0]})
    day = date(2026, 1, 5)

    for d in range(days):
        for s in SYMBOLS:
            prices[s] = max(1.0, prices[s] * (1 + rng.gauss(0, 0.03)))
        broker.advance(dict(prices))
        if chaos:
            r = rng.random()
            if r < 0.08:
                broker.fail_next_cancel = True
            elif r < 0.16:
                broker.fail_next_submit = True
            elif r < 0.22:
                broker.fail_next_read = True
            elif r < 0.26:
                try:
                    os.unlink(position_state.STATE_PATH)   # memoria persa
                except OSError:
                    pass
            elif r < 0.30:
                sym = rng.choice(SYMBOLS)
                if sym not in broker.positions:            # posizione comparsa a mano
                    broker.positions[sym] = Position(sym, rng.randint(1, 20), prices[sym], prices[sym])
                    foreign.add(sym)

        # Regola 9: le esecuzioni avvengono in seduta, il ciclo gira dopo la
        # chiusura. Una posizione eseguita ieri e' rimasta scoperta tutta la
        # notte se il suo stop non era gia' al broker: va guardata PRIMA che
        # il ciclo di oggi abbia occasione di rimediare.
        for sym, pos in broker.positions.items():
            if sym in foreign or sym in bot.LONG_TERM_TICKERS or sym not in opened_before:
                continue
            stops = sum(o.qty for o in broker.orders
                        if o.symbol == sym and o.side == "sell" and o.type == "stop")
            if stops < pos.qty:
                violations.append(
                    f"giorno {d}: {sym} ha passato la notte con {pos.qty} azioni e stop per {stops}")

        cands = [_candidate(s, prices[s], rng) for s in rng.sample(SYMBOLS, rng.randint(0, 12))]
        with patch.object(bot, "Broker", return_value=broker), \
             patch.object(bot, "screen_universe", return_value=cands), \
             patch.object(bot, "_print_candidate"), \
             patch.object(bot, "get_daily_bars", return_value=falling), \
             patch.object(bot, "market_today", return_value=day), \
             patch.object(bot.notify, "alert", side_effect=lambda m, level="info": alerts.append((level, m))):
            try:
                bot.cmd_short_term_once(argparse.Namespace(execute=True))
            except Exception as exc:
                violations.append(f"giorno {d}: il ciclo ha sollevato {type(exc).__name__}: {exc}")
        _check(broker, d, violations, foreign, alerts)
        foreign &= set(broker.positions)
        opened_before = set(broker.positions)
        alerts.clear()
        day += timedelta(days=1)
    return violations


def test_the_bot_never_breaks_its_own_rules_in_normal_conditions(tmp_path):
    for seed in range(2):
        assert _run(seed, days=30, chaos=False, tmp_path=tmp_path) == []


def test_the_bot_never_breaks_its_own_rules_under_injected_failures(tmp_path):
    """Cancellazioni rifiutate, invii rifiutati, errori di rete in lettura,
    file di stato cancellato, posizioni comparse dal nulla."""
    for seed in range(3):
        assert _run(seed, days=30, chaos=True, tmp_path=tmp_path) == []


# --- Lungo termine sotto guasti --------------------------------------------
# Anche Harry Browne manda ordini veri (acquisti e vendite a mercato) e non
# era mai stato messo sotto stress. Le sue regole: non ribilanciare piu' di
# una volta per periodo, non segnare come fatto un ciclo fallito, non
# spendere piu' della cassa disponibile.

def _long_term_run(seed, days, tmp_path):
    rng = random.Random(seed)
    broker = FakeBroker(cash=30_000.0)
    violations, marked_days = [], []
    position_state.STATE_PATH = str(tmp_path / f"lt-{seed}.json")
    day = date(2026, 1, 5)
    prices = {t: rng.uniform(50, 400) for t in bot.config.HARRY_BROWNE_TICKERS}

    for d in range(days):
        for t in prices:
            prices[t] = max(1.0, prices[t] * (1 + rng.gauss(0, 0.01)))
        broker.last_prices.update(prices)
        if rng.random() < 0.15:
            broker.fail_next_submit = True          # un ordine rifiutato
        cash_before = broker.cash
        with patch.object(bot, "_last_close", side_effect=lambda t: prices[t]), \
             patch.object(bot.notify, "alert"), \
             patch.object(bot.config, "LONG_TERM_AUTO_STRATEGY", "harry_browne"):
            try:
                bot.run_long_term_cycle(broker, execute=True, today=day)
            except Exception as exc:
                violations.append(f"giorno {d}: il ciclo di lungo termine ha sollevato {exc}")
        last = position_state.get_meta("harry_browne_last_rebalance")
        if last and last not in marked_days:
            marked_days.append(last)
        if broker.cash < -0.01:
            violations.append(f"giorno {d}: cassa negativa nel lungo termine")
        if broker.rejections:
            violations.append(f"giorno {d}: rifiuti dal broker {broker.rejections[:2]}")
            broker.rejections.clear()
        invested = sum(p.qty * prices.get(p.symbol, p.current_price) for p in broker.positions.values())
        if invested > bot.config.LONG_TERM_CAPITAL * 1.5:
            violations.append(f"giorno {d}: investiti {invested:.0f} contro un capitale di {bot.config.LONG_TERM_CAPITAL:.0f}")
        day += timedelta(days=1)

    # un solo ribilanciamento per trimestre, non uno al giorno
    if len(marked_days) > 1 + days // 90:
        violations.append(f"{len(marked_days)} ribilanciamenti in {days} giorni: troppi")
    return violations


def _monthly_frame(ticker, today, rng):
    """Chiusure mensili su ~5 anni, cammino casuale abbastanza mosso da
    incrociare la SMA10 in entrambe le direzioni durante la simulazione:
    servono sia i mesi "dentro" sia quelli "fuori"."""
    months = pd.date_range(end=pd.Timestamp(today).to_period("M").to_timestamp("M"), periods=64, freq="ME")
    price, closes = rng.uniform(50, 300), []
    for _ in months:
        price = max(1.0, price * (1 + rng.gauss(0.004, 0.06)))
        closes.append(price)
    return pd.DataFrame({"close": closes}, index=months)


def _advanced_run(seed, days, tmp_path):
    """L'altro ramo del lungo termine -- e quello che gira davvero, visto
    che LONG_TERM_AUTO_STRATEGY vale "advanced" di default. La simulazione
    lo saltava del tutto: fissava "harry_browne" e lasciava scoperta la
    strategia realmente in uso."""
    rng = random.Random(1000 + seed)
    broker = FakeBroker(cash=30_000.0)
    violations, months_marked = [], []
    position_state.STATE_PATH = str(tmp_path / f"adv-{seed}.json")
    day = date(2026, 1, 5)
    tickers = list(bot.config.ADVANCED_TICKERS)
    prices = {t: rng.uniform(50, 300) for t in tickers}
    frames = {t: _monthly_frame(t, day + timedelta(days=days), rng) for t in tickers}

    for d in range(days):
        for t in prices:
            prices[t] = max(1.0, prices[t] * (1 + rng.gauss(0, 0.012)))
        broker.last_prices.update(prices)
        if rng.random() < 0.15:
            broker.fail_next_submit = True          # un ordine rifiutato
        marked_before = position_state.get_meta("advanced_last_month")
        alerts: list[tuple[str, str]] = []
        with patch.object(bot, "_last_close", side_effect=lambda t: prices[t]), \
             patch.object(bot, "get_monthly_bars", side_effect=lambda t, period="10y": frames[t]), \
             patch.object(bot.notify, "alert", side_effect=lambda m, level="info": alerts.append((level, m))), \
             patch.object(bot.config, "LONG_TERM_AUTO_STRATEGY", "advanced"):
            try:
                bot.run_long_term_cycle(broker, execute=True, today=day)
            except Exception as exc:
                violations.append(f"giorno {d}: il ciclo Advanced ha sollevato {type(exc).__name__}: {exc}")

        marked = position_state.get_meta("advanced_last_month")
        # Un mese con un asset andato storto NON va segnato come fatto:
        # segnandolo, quell'asset resterebbe fuori posizione per un mese
        # intero senza che nessuno riprovi. Il ciclo lo dice con un avviso
        # di errore, quindi le due cose non possono coesistere nello stesso
        # giro. Senza questo controllo la simulazione non vedeva la
        # differenza fra "segna solo se e' andato tutto bene" e "segna
        # comunque".
        if marked != marked_before and any(level == "error" for level, _ in alerts):
            violations.append(
                f"giorno {d}: mese {marked} segnato come completato nonostante un errore su un asset")
        if marked and marked not in months_marked:
            months_marked.append(marked)
        if broker.cash < -0.01:
            violations.append(f"giorno {d}: cassa negativa nel ciclo Advanced ({broker.cash:.2f})")
        if broker.rejections:
            violations.append(f"giorno {d}: rifiuti dal broker {broker.rejections[:2]}")
            broker.rejections.clear()
        invested = sum(p.qty * prices.get(p.symbol, p.current_price) for p in broker.positions.values())
        if invested > bot.config.LONG_TERM_CAPITAL * 1.5:
            violations.append(
                f"giorno {d}: investiti {invested:.0f} contro un capitale di {bot.config.LONG_TERM_CAPITAL:.0f}")
        day += timedelta(days=1)

    # Una decisione al mese, non una al giorno: il mese si segna come fatto
    # e non si riapre.
    if len(months_marked) > days // 28 + 1:
        violations.append(f"{len(months_marked)} mesi processati in {days} giorni: troppi")
    return violations


def test_the_advanced_cycle_holds_under_rejected_orders(tmp_path):
    for seed in range(3):
        assert _advanced_run(seed, days=120, tmp_path=tmp_path) == []


def test_the_long_term_cycle_holds_under_rejected_orders(tmp_path):
    for seed in range(3):
        assert _long_term_run(seed, days=120, tmp_path=tmp_path) == []
