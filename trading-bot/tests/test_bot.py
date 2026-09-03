"""Test della logica di orchestrazione in bot.py con Broker e screener
mockati -- nessuna chiamata di rete, nessun ordine reale."""
import argparse
from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import requests

import bot
from short_term import levels as levels_mod
from short_term.patterns import PatternMatch
from short_term.screener import Candidate
from short_term.trend import TrendQualification


def _position(symbol, qty, entry_price, current_price):
    return {"symbol": symbol, "qty": qty, "avg_entry_price": entry_price, "current_price": current_price}


def _candidate(symbol, direction="long", entry=100.0, stop=95.0, qty=10) -> Candidate:
    tq = TrendQualification(direction=direction, score=3, satisfied={})
    match = PatternMatch("Pullback Semplice", direction, setup_bar_index=0, pullback_bar_count=3)
    lv = levels_mod.EntryLevels(direction=direction, entry=entry, stop_loss=stop, risk_per_share=abs(entry - stop))
    return Candidate(
        symbol=symbol,
        direction=direction,
        pattern=match.pattern,
        trend=tq,
        levels=lv,
        qty=qty,
        ribbon_aligned=True,
        sector_etf="XLK",
        sector_passes=True,
        earnings_warn=False,
        sr_too_close=False,
        price_blocks_trade=False,
        has_divergence=False,
    )


class _FakeState:
    """Sostituto in-memory di common/position_state.py per i test, cosi'
    non si scrive mai un vero file di stato su disco durante la suite."""

    def __init__(self, initial=None, meta=None):
        self.data = {k: dict(v) for k, v in (initial or {}).items()}
        self.meta = dict(meta or {})

    def get(self, symbol):
        return self.data.get(symbol, {})

    def set_fields(self, symbol, **fields):
        self.data.setdefault(symbol, {}).update(fields)

    def clear(self, symbol):
        self.data.pop(symbol, None)

    def tracked_symbols(self):
        return list(self.data.keys())

    def get_meta(self, key, default=None):
        return self.meta.get(key, default)

    def set_meta(self, key, value):
        self.meta[key] = value


@contextmanager
def _patched_state(initial=None, meta=None):
    fake = _FakeState(initial, meta)
    with patch("bot.position_state.get", side_effect=fake.get), \
         patch("bot.position_state.set_fields", side_effect=fake.set_fields), \
         patch("bot.position_state.clear", side_effect=fake.clear), \
         patch("bot.position_state.tracked_symbols", side_effect=fake.tracked_symbols), \
         patch("bot.position_state.get_meta", side_effect=fake.get_meta), \
         patch("bot.position_state.set_meta", side_effect=fake.set_meta):
        yield fake


def _broker(positions=(), open_orders=None):
    broker = MagicMock()
    broker.list_open_positions.return_value = list(positions)
    broker.list_open_orders.return_value = [] if open_orders is None else open_orders
    broker.get_open_position.return_value = None
    return broker


ENTERED_10 = {"risk_per_share": 5.0, "original_qty": 10, "stage": "entered", "stop_price": 95.0, "direction": "long"}


def test_tranches_match_backtest_arithmetic():
    assert bot._tranches(10) == (5, 3, 2)
    assert bot._tranches(7) == (3, 2, 2)
    assert bot._tranches(3) == (1, 0, 2)
    assert bot._tranches(1) == (0, 0, 1)


# --- stadio pending -> entered ------------------------------------------------

def test_filled_pending_entry_becomes_entered_with_actual_qty():
    broker = _broker([_position("AAPL", 8, 100.0, 101.0)])  # eseguite 8 delle 10 pianificate

    with _patched_state({"AAPL": {**ENTERED_10, "stage": "pending", "original_qty": 10}}) as state:
        bot.manage_open_short_term_positions(broker)

    assert state.data["AAPL"]["stage"] == "entered"
    assert state.data["AAPL"]["original_qty"] == 8
    # nessun ordine di uscita al broker -> struttura riemessa sulla size reale: meta' (4) OCO, 4 stop
    broker.submit_oco_exit.assert_called_once_with("AAPL", 4, "long", 105.0, 95.0)
    broker.submit_stop.assert_called_once_with("AAPL", 4, 95.0, "long")


# --- stadio entered -------------------------------------------------------------

def test_entered_without_exit_orders_places_oco_half_and_stop_half():
    broker = _broker([_position("AAPL", 10, 100.0, 101.0)])

    with _patched_state({"AAPL": ENTERED_10}):
        bot.manage_open_short_term_positions(broker)

    broker.cancel_open_orders.assert_called_once_with("AAPL")
    broker.submit_oco_exit.assert_called_once_with("AAPL", 5, "long", 105.0, 95.0)  # T1 = 100 + 1R(5), stop 95
    broker.submit_stop.assert_called_once_with("AAPL", 5, 95.0, "long")


def test_entered_with_exit_orders_present_does_nothing():
    broker = _broker([_position("AAPL", 10, 100.0, 104.0)], open_orders=[MagicMock()])

    with _patched_state({"AAPL": ENTERED_10}) as state:
        bot.manage_open_short_term_positions(broker)

    broker.submit_oco_exit.assert_not_called()
    broker.submit_stop.assert_not_called()
    assert state.data["AAPL"]["stage"] == "entered"


def test_t1_filled_moves_to_1r_done_with_3r_oco_and_breakeven_stop():
    # il limit a T1 ha venduto 5 delle 10: restano 5 -> OCO su 3 (limit 3R=115 / stop pareggio 100) + stop pareggio su 2
    broker = _broker([_position("AAPL", 5, 100.0, 106.0)], open_orders=[MagicMock()])

    with _patched_state({"AAPL": ENTERED_10}) as state:
        bot.manage_open_short_term_positions(broker)

    broker.cancel_open_orders.assert_called_once_with("AAPL")
    broker.submit_oco_exit.assert_called_once_with("AAPL", 3, "long", 115.0, 100.0)
    broker.submit_stop.assert_called_once_with("AAPL", 2, 100.0, "long")
    assert state.data["AAPL"]["stage"] == "1R_done"


def test_t1_filled_short_math():
    # short: entrata 100, rischio 5 -> T3 = 85, pareggio 100
    broker = _broker([_position("TSLA", -5, 100.0, 94.0)], open_orders=[MagicMock()])

    with _patched_state({"TSLA": {**ENTERED_10, "direction": "short", "stop_price": 105.0}}) as state:
        bot.manage_open_short_term_positions(broker)

    broker.submit_oco_exit.assert_called_once_with("TSLA", 3, "short", 85.0, 100.0)
    broker.submit_stop.assert_called_once_with("TSLA", 2, 100.0, "short")
    assert state.data["TSLA"]["stage"] == "1R_done"


def test_single_share_position_moves_stop_to_breakeven_at_1r():
    broker = _broker([_position("AAPL", 1, 100.0, 106.0)], open_orders=[MagicMock()])

    with _patched_state({"AAPL": {**ENTERED_10, "original_qty": 1}}) as state:
        bot.manage_open_short_term_positions(broker)

    broker.submit_oco_exit.assert_not_called()
    broker.submit_stop.assert_called_once_with("AAPL", 1, 100.0, "long")
    assert state.data["AAPL"]["stage"] == "1R_done"


def test_entered_without_exit_orders_and_without_saved_stop_alerts_and_does_not_invent_one():
    broker = _broker([_position("AAPL", 10, 100.0, 102.0)])

    with _patched_state({"AAPL": {"risk_per_share": 5.0, "original_qty": 10, "stage": "entered"}}), \
         patch("bot.notify.alert") as alert:
        bot.manage_open_short_term_positions(broker)

    broker.submit_oco_exit.assert_not_called()
    broker.submit_stop.assert_not_called()
    assert any(kw.get("level") == "error" for _, kw in alert.call_args_list)


# --- stadio 1R_done e runner --------------------------------------------------

def test_3r_filled_moves_to_runner_with_breakeven_stop():
    broker = _broker([_position("AAPL", 2, 100.0, 116.0)], open_orders=[MagicMock()])

    with _patched_state({"AAPL": {**ENTERED_10, "stage": "1R_done"}}) as state:
        bot.manage_open_short_term_positions(broker)

    broker.cancel_open_orders.assert_called_once_with("AAPL")
    broker.submit_stop.assert_called_once_with("AAPL", 2, 100.0, "long")
    broker.submit_oco_exit.assert_not_called()
    assert state.data["AAPL"]["stage"] == "3R_done"


def test_1r_done_without_exit_orders_replaces_structure():
    broker = _broker([_position("AAPL", 5, 100.0, 108.0)])

    with _patched_state({"AAPL": {**ENTERED_10, "stage": "1R_done"}}) as state:
        bot.manage_open_short_term_positions(broker)

    broker.submit_oco_exit.assert_called_once_with("AAPL", 3, "long", 115.0, 100.0)
    broker.submit_stop.assert_called_once_with("AAPL", 2, 100.0, "long")
    assert state.data["AAPL"]["stage"] == "1R_done"


def test_1r_done_with_orders_and_no_3r_fill_does_nothing():
    broker = _broker([_position("AAPL", 5, 100.0, 108.0)], open_orders=[MagicMock()])

    with _patched_state({"AAPL": {**ENTERED_10, "stage": "1R_done"}}):
        bot.manage_open_short_term_positions(broker)

    broker.submit_oco_exit.assert_not_called()
    broker.submit_stop.assert_not_called()


def test_runner_exits_on_long_term_ma_reversal():
    broker = _broker([_position("AAPL", 2, 100.0, 130.0)], open_orders=[MagicMock()])
    closes = pd.Series(list(range(100, 300)))
    bars = pd.DataFrame({"close": closes[::-1].reset_index(drop=True)})  # discendente -> chiusura sotto SMA200

    with _patched_state({"AAPL": {**ENTERED_10, "stage": "3R_done"}}) as state, \
         patch("bot.get_daily_bars", return_value=bars):
        bot.manage_open_short_term_positions(broker)

    broker.flatten.assert_called_once_with("AAPL")
    assert "AAPL" not in state.data


def test_runner_holds_without_reversal_and_replaces_missing_stop():
    broker = _broker([_position("AAPL", 2, 100.0, 130.0)])  # nessun ordine aperto
    bars = pd.DataFrame({"close": pd.Series(list(range(100, 300)))})  # salente -> sopra SMA200

    with _patched_state({"AAPL": {**ENTERED_10, "stage": "3R_done"}}), \
         patch("bot.get_daily_bars", return_value=bars):
        bot.manage_open_short_term_positions(broker)

    broker.flatten.assert_not_called()
    broker.submit_stop.assert_called_once_with("AAPL", 2, 100.0, "long")


# --- casi limite e isolamento ---------------------------------------------------

def test_no_saved_state_is_skipped_safely():
    broker = _broker([_position("AAPL", 10, 100.0, 200.0)])

    with _patched_state({}):
        bot.manage_open_short_term_positions(broker)

    broker.submit_oco_exit.assert_not_called()
    broker.submit_stop.assert_not_called()


def test_long_term_etfs_are_ignored_by_short_term_management():
    etf = bot.config.ADVANCED_TICKERS[0]
    broker = _broker([_position(etf, 10, 100.0, 200.0)])

    with _patched_state({}):
        bot.manage_open_short_term_positions(broker)

    broker.submit_stop.assert_not_called()
    broker.cancel_open_orders.assert_not_called()


def test_orphan_cleanup_clears_closed_positions_but_keeps_pending_entries():
    broker = _broker([])

    with _patched_state({
        "OLDSYM": {**ENTERED_10, "stage": "1R_done"},
        "WAITING": {**ENTERED_10, "stage": "pending"},
    }) as state:
        bot.manage_open_short_term_positions(broker)

    assert "OLDSYM" not in state.data
    assert "WAITING" in state.data


def test_one_symbol_error_does_not_block_others():
    broker = _broker([_position("BAD", 10, 100.0, 106.0), _position("AAPL", 5, 100.0, 106.0)], open_orders=[MagicMock()])

    def _get(symbol):
        if symbol == "BAD":
            raise ConnectionError("rete giu'")
        return dict(ENTERED_10)

    with patch("bot.position_state.get", side_effect=_get), \
         patch("bot.position_state.set_fields"), \
         patch("bot.position_state.clear"), \
         patch("bot.position_state.tracked_symbols", return_value=[]):
        bot.manage_open_short_term_positions(broker)  # non deve sollevare eccezioni

    broker.submit_oco_exit.assert_called_once_with("AAPL", 3, "long", 115.0, 100.0)


def test_short_term_equity_excludes_long_term_etf_value(monkeypatch):
    monkeypatch.setattr(bot.config, "SHORT_TERM_CAPITAL", 0.0)  # nessun tetto
    broker = MagicMock()
    etf = bot.config.HARRY_BROWNE_TICKERS[0]
    broker.get_equity.return_value = 10_000.0
    broker.list_open_positions.return_value = [_position(etf, 10, 100.0, 300.0)]

    assert bot._short_term_equity(broker) == 7_000.0


def test_short_term_equity_is_capped_at_the_allocated_capital(monkeypatch):
    """Conto paper da 100.000$ ma si vuole far muovere al bot solo 10.000:
    il rischio dell'1% deve valere sui 10.000, non sul conto intero."""
    monkeypatch.setattr(bot.config, "SHORT_TERM_CAPITAL", 10_000.0)
    broker = MagicMock()
    broker.get_equity.return_value = 100_000.0
    broker.list_open_positions.return_value = []

    assert bot._short_term_equity(broker) == 10_000.0


def test_short_term_equity_follows_the_account_when_below_the_cap(monkeypatch):
    monkeypatch.setattr(bot.config, "SHORT_TERM_CAPITAL", 10_000.0)
    broker = MagicMock()
    broker.get_equity.return_value = 6_000.0  # il conto e' sceso sotto il tetto
    broker.list_open_positions.return_value = []

    assert bot._short_term_equity(broker) == 6_000.0


def test_short_term_cash_leaves_room_only_up_to_the_allocated_capital(monkeypatch):
    """Dodici posizioni dimensionate sull'1% di 10.000 potrebbero comunque
    impegnare molto piu' di 10.000: la cassa spendibile e' il tetto meno
    quanto e' gia' investito nel breve termine."""
    monkeypatch.setattr(bot.config, "SHORT_TERM_CAPITAL", 10_000.0)
    broker = MagicMock()
    broker.get_cash.return_value = 100_000.0
    broker.list_open_positions.return_value = [_position("AAPL", 30, 200.0, 250.0)]  # 7.500 investiti

    assert bot._short_term_cash(broker) == 2_500.0


def test_short_term_cash_never_exceeds_real_cash(monkeypatch):
    monkeypatch.setattr(bot.config, "SHORT_TERM_CAPITAL", 10_000.0)
    broker = MagicMock()
    broker.get_cash.return_value = 800.0  # niente leva: la cassa vera comanda
    broker.list_open_positions.return_value = []

    assert bot._short_term_cash(broker) == 800.0


def test_short_term_cash_is_zero_when_the_allocation_is_fully_invested(monkeypatch):
    monkeypatch.setattr(bot.config, "SHORT_TERM_CAPITAL", 10_000.0)
    broker = MagicMock()
    broker.get_cash.return_value = 50_000.0
    broker.list_open_positions.return_value = [_position("AAPL", 60, 200.0, 200.0)]  # 12.000 > tetto

    assert bot._short_term_cash(broker) == 0.0


# --- ingressi pendenti: riconciliazione ------------------------------------------

PENDING = {**ENTERED_10, "stage": "pending", "entry": 100.0, "pending_since": "2026-09-01"}


def test_pending_entry_kept_while_setup_still_valid():
    broker = _broker(open_orders=[MagicMock()])

    with _patched_state({"AAPL": PENDING}) as state:
        bot.reconcile_pending_entries(broker, {"AAPL"}, date(2026, 9, 2))

    broker.cancel_open_orders.assert_not_called()
    assert "AAPL" in state.data


def test_pending_entry_cancelled_when_setup_gone():
    broker = _broker(open_orders=[MagicMock()])

    with _patched_state({"AAPL": PENDING}) as state:
        bot.reconcile_pending_entries(broker, set(), date(2026, 9, 2))

    broker.cancel_open_orders.assert_called_once_with("AAPL")
    assert "AAPL" not in state.data


def test_pending_entry_cancelled_when_expired():
    broker = _broker(open_orders=[MagicMock()])

    with _patched_state({"AAPL": PENDING}) as state:
        bot.reconcile_pending_entries(broker, {"AAPL"}, date(2026, 10, 15))

    broker.cancel_open_orders.assert_called_once_with("AAPL")
    assert "AAPL" not in state.data


def test_pending_entry_cleared_when_order_no_longer_open_and_no_position():
    broker = _broker(open_orders=[])

    with _patched_state({"AAPL": PENDING}) as state:
        bot.reconcile_pending_entries(broker, {"AAPL"}, date(2026, 9, 2))

    assert "AAPL" not in state.data


def test_pending_entry_left_alone_once_position_exists():
    broker = _broker(open_orders=[])
    broker.get_open_position.return_value = {"symbol": "AAPL", "qty": 10.0}

    with _patched_state({"AAPL": PENDING}) as state:
        bot.reconcile_pending_entries(broker, set(), date(2026, 9, 2))

    broker.cancel_open_orders.assert_not_called()
    assert "AAPL" in state.data


# --- cmd_short_term_once: ingresso con ordine stop ------------------------------

def _cycle_broker(cash=1_000_000.0, equity=10_000.0):
    broker = _broker()
    broker.is_market_open.return_value = True
    broker.is_trading_day.return_value = True
    broker.get_equity.return_value = equity
    broker.get_cash.return_value = cash
    return broker


def test_cmd_short_term_once_submits_stop_entries_and_stops_at_aggregate_risk_cap(monkeypatch):
    monkeypatch.setattr(bot.config, "SHORT_TERM_CAPITAL", 0.0)  # nessun tetto di capitale: si testa quello di rischio
    candidates = [_candidate(f"SYM{i}") for i in range(20)]  # ben oltre il tetto (12% / 1% = 12)
    broker = _cycle_broker()

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"), \
         _patched_state() as state:
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    assert broker.submit_stop_entry.call_count == 12
    broker.enter_with_stop.assert_not_called()  # mai a mercato
    first = broker.submit_stop_entry.call_args_list[0][0]
    assert first == ("SYM0", 10, "long", 100.0, 95.0)
    assert state.data["SYM0"]["stage"] == "pending"
    assert state.data["SYM0"]["entry"] == 100.0 and state.data["SYM0"]["stop_price"] == 95.0


def test_pending_entries_count_toward_aggregate_risk_cap():
    pending = {f"PEND{i}": {**PENDING, "entry": 100.0, "stop_price": 95.0} for i in range(11)}
    # i pendenti restano candidati con gli STESSI livelli (quindi non vengono ne' cancellati ne' risottomessi)
    candidates = [_candidate(f"PEND{i}") for i in range(11)] + [_candidate(f"SYM{i}") for i in range(20)]
    broker = _cycle_broker()
    broker.list_open_orders.return_value = [MagicMock()]  # ordini pendenti vivi

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"), \
         _patched_state(pending):
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    assert broker.submit_stop_entry.call_count == 1  # 11 pendenti + 1 nuovo = 12
    assert broker.submit_stop_entry.call_args[0][0] == "SYM0"


def test_pending_entry_with_new_levels_is_replaced_not_duplicated():
    candidates = [_candidate("AAPL", entry=102.0, stop=97.0)]  # barra di setup spostata
    broker = _cycle_broker()
    broker.list_open_orders.return_value = [MagicMock()]

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"), \
         _patched_state({"AAPL": PENDING}) as state:
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    broker.cancel_open_orders.assert_called_with("AAPL")
    broker.submit_stop_entry.assert_called_once_with("AAPL", 10, "long", 102.0, 97.0)
    assert state.data["AAPL"]["entry"] == 102.0
    assert state.data["AAPL"]["pending_since"] == "2026-09-01"  # la data originale resta


def test_cmd_short_term_once_skips_symbol_already_in_position():
    candidates = [_candidate("AAPL"), _candidate("MSFT")]
    broker = _cycle_broker()
    broker.get_open_position.side_effect = lambda s: {"symbol": "AAPL", "qty": 10.0} if s == "AAPL" else None

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"), \
         _patched_state():
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    broker.submit_stop_entry.assert_called_once()
    assert broker.submit_stop_entry.call_args[0][0] == "MSFT"


def test_cmd_short_term_once_non_trading_day_does_nothing():
    """Weekend o festivo: nessuna seduta, niente da analizzare. Nota che il
    ciclo gira DOPO la chiusura, quindi "mercato aperto adesso" sarebbe
    sempre falso e non e' il controllo giusto."""
    broker = MagicMock()
    broker.is_trading_day.return_value = False

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe") as mock_screen:
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    mock_screen.assert_not_called()
    broker.list_open_positions.assert_not_called()


def test_cmd_short_term_once_runs_after_close_on_a_trading_day():
    """Il ciclo deve girare a mercato CHIUSO purche' oggi ci sia stata una
    seduta: gli ordini sono GTC e restano in coda per la riapertura."""
    broker = _cycle_broker()
    broker.is_market_open.return_value = False  # dopo la chiusura
    broker.is_trading_day.return_value = True

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe", return_value=[_candidate("AAPL")]), \
         patch("bot._print_candidate"), \
         _patched_state():
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    broker.submit_stop_entry.assert_called_once()


def test_cmd_short_term_once_report_only_never_submits_orders():
    candidates = [_candidate("AAPL"), _candidate("MSFT")]
    broker = _cycle_broker()

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"), \
         _patched_state() as state:
        bot.cmd_short_term_once(argparse.Namespace(execute=False))

    broker.submit_stop_entry.assert_not_called()
    assert state.data == {}


def test_cmd_short_term_once_failed_order_does_not_block_next_candidate_or_count_toward_cap():
    candidates = [_candidate("BAD"), _candidate("MSFT")]
    broker = _cycle_broker()
    broker.submit_stop_entry.side_effect = [ConnectionError("ordine rifiutato"), None]

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"), \
         _patched_state() as state:
        bot.cmd_short_term_once(argparse.Namespace(execute=True))  # non deve sollevare eccezioni

    assert broker.submit_stop_entry.call_count == 2
    assert broker.submit_stop_entry.call_args_list[1][0][0] == "MSFT"
    assert "BAD" not in state.data and "MSFT" in state.data


def test_allocated_capital_can_bind_before_the_aggregate_risk_cap(monkeypatch):
    """Con 10.000 destinati al breve termine e posizioni da 1.000 di
    controvalore, la cassa finisce alla decima: il tetto di rischio (12)
    non viene nemmeno raggiunto."""
    monkeypatch.setattr(bot.config, "SHORT_TERM_CAPITAL", 10_000.0)
    candidates = [_candidate(f"SYM{i}", entry=100.0, stop=95.0, qty=10) for i in range(20)]
    broker = _cycle_broker(cash=1_000_000.0)

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"), \
         _patched_state():
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    assert broker.submit_stop_entry.call_count == 10


def test_short_term_position_count_excludes_long_term_etfs(monkeypatch):
    monkeypatch.setattr(bot.config, "SHORT_TERM_CAPITAL", 0.0)
    candidates = [_candidate(f"SYM{i}") for i in range(20)]
    etf = bot.config.ADVANCED_TICKERS[0]
    broker = _cycle_broker()
    broker.list_open_positions.return_value = [_position(etf, 1, 1.0, 1.0)] * 11  # ETF: non contano nel tetto

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"), \
         _patched_state():
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    assert broker.submit_stop_entry.call_count == 12


def test_cash_cap_limits_position_size_and_is_consumed_across_candidates():
    candidates = [_candidate("AAA", entry=100.0, stop=95.0, qty=10), _candidate("BBB", entry=100.0, stop=95.0, qty=10)]
    broker = _cycle_broker(cash=1_500.0)  # basta per 10 azioni della prima e 5 della seconda

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"), \
         _patched_state() as state:
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    calls = broker.submit_stop_entry.call_args_list
    assert [(c[0][0], c[0][1]) for c in calls] == [("AAA", 10), ("BBB", 5)]
    assert state.data["BBB"]["original_qty"] == 5
    assert state.data["BBB"]["stop_price"] == 95.0


def test_cash_cap_skips_candidate_when_not_even_one_share_is_affordable():
    broker = _cycle_broker(cash=50.0)

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe", return_value=[_candidate("AAA")]), \
         patch("bot._print_candidate"), \
         _patched_state():
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    broker.submit_stop_entry.assert_not_called()


def test_drawdown_brake_blocks_new_entries_but_not_management(monkeypatch):
    monkeypatch.setattr(bot.config, "SHORT_TERM_MAX_DRAWDOWN_PCT", 15.0)
    broker = _cycle_broker(equity=8_000.0)  # -20% dal massimo di 10.000
    broker.list_open_positions.return_value = [_position("AAPL", 10, 100.0, 101.0)]

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe", return_value=[_candidate("MSFT")]), \
         patch("bot._print_candidate"), \
         _patched_state({"AAPL": ENTERED_10}, meta={"equity_history": [["2026-01-02", 10_000.0]]}) as state:
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    broker.submit_stop_entry.assert_not_called()  # niente nuove entrate
    broker.submit_oco_exit.assert_called_once()  # ma la posizione aperta e' stata gestita
    assert max(v for _, v in state.meta["equity_history"]) == 10_000.0


def test_drawdown_brake_releases_after_a_year_of_flat_equity(monkeypatch):
    """Il bug: col massimo storico ASSOLUTO il freno non si sblocca mai --
    bloccate le entrate, l'equity resta ferma, il picco resta irraggiungibile.
    Nel backtest il bot si spegneva nel 2020 e non operava piu' fino al 2026.
    Col massimo su finestra mobile, dopo un anno il vecchio picco esce dalla
    finestra e il freno si rilascia da solo."""
    monkeypatch.setattr(bot.config, "SHORT_TERM_MAX_DRAWDOWN_PCT", 15.0)
    broker = MagicMock()
    broker.get_equity.return_value = 8_000.0  # -20% dal picco di 10.000

    with _patched_state(meta={"equity_history": [["2026-01-02", 10_000.0]]}) as state:
        # giorno del crollo: il freno scatta
        assert bot._drawdown_brake_active(broker, date(2026, 1, 5)) is True
        # equity ferma per un anno: il picco vecchio esce dalla finestra
        for i in range(1, bot.EQUITY_HISTORY_DAYS + 1):
            active = bot._drawdown_brake_active(broker, date(2026, 1, 5) + timedelta(days=i))
        assert active is False, "il freno deve rilasciarsi, non bloccare il bot per sempre"
        assert len(state.meta["equity_history"]) <= bot.EQUITY_HISTORY_DAYS


def test_drawdown_brake_seeds_peak_from_the_first_sample(monkeypatch):
    monkeypatch.setattr(bot.config, "SHORT_TERM_MAX_DRAWDOWN_PCT", 15.0)
    broker = MagicMock()
    broker.get_equity.return_value = 10_000.0

    with _patched_state():
        # primo giorno in assoluto: nessuno storico, nessun freno
        assert bot._drawdown_brake_active(broker, date(2026, 1, 5)) is False


def test_drawdown_brake_keeps_one_sample_per_day(monkeypatch):
    monkeypatch.setattr(bot.config, "SHORT_TERM_MAX_DRAWDOWN_PCT", 15.0)
    broker = MagicMock()
    broker.get_equity.return_value = 10_000.0

    with _patched_state() as state:
        bot._drawdown_brake_active(broker, date(2026, 1, 5))
        broker.get_equity.return_value = 9_900.0
        bot._drawdown_brake_active(broker, date(2026, 1, 5))  # stesso giorno, riesecuzione

    assert len(state.meta["equity_history"]) == 1
    assert state.meta["equity_history"][0][1] == 9_900.0  # tenuto il valore piu' recente


def test_drawdown_brake_disabled_when_threshold_is_zero(monkeypatch):
    monkeypatch.setattr(bot.config, "SHORT_TERM_MAX_DRAWDOWN_PCT", 0.0)
    broker = MagicMock()
    broker.get_equity.return_value = 1.0

    with _patched_state(meta={"equity_history": [["2026-01-01", 10_000.0]]}):
        assert bot._drawdown_brake_active(broker, date(2026, 1, 5)) is False


def test_drawdown_brake_updates_peak_and_allows_entries_within_limit(monkeypatch):
    monkeypatch.setattr(bot.config, "SHORT_TERM_MAX_DRAWDOWN_PCT", 15.0)
    broker = _cycle_broker(equity=12_000.0)

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe", return_value=[_candidate("MSFT")]), \
         patch("bot._print_candidate"), \
         _patched_state(meta={"equity_history": [["2026-01-02", 10_000.0]]}) as state:
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    broker.submit_stop_entry.assert_called_once()
    assert max(v for _, v in state.meta["equity_history"]) == 12_000.0


# --- ciclo automatico di lungo termine --------------------------------------------

def _monthly_closes(values):
    idx = pd.date_range("2020-01-31", periods=len(values), freq="ME")
    return pd.DataFrame({"close": pd.Series(values, index=idx)})


def _fake_state_meta():
    meta = {}
    return meta, patch("bot.position_state.get_meta", side_effect=lambda k, d=None: meta.get(k, d)), \
        patch("bot.position_state.set_meta", side_effect=lambda k, v: meta.__setitem__(k, v))


def test_advanced_cycle_buys_asset_above_sma_when_not_holding(monkeypatch):
    monkeypatch.setattr(bot.config, "LONG_TERM_AUTO_STRATEGY", "advanced")
    monkeypatch.setattr(bot.config, "LONG_TERM_CAPITAL", 10_000.0)
    broker = MagicMock()
    broker.get_cash.return_value = 10_000.0
    broker.get_open_position.return_value = None
    rising = _monthly_closes(list(range(100, 130)))

    meta, p_get, p_set = _fake_state_meta()
    with p_get, p_set, \
         patch("bot.get_monthly_bars", return_value=rising), \
         patch("bot._last_close", return_value=100.0):
        bot.run_long_term_cycle(broker, execute=True, today=date(2026, 9, 2))

    assert broker.buy_market.call_count == len(bot.config.ADVANCED_TICKERS)
    broker.sell_market.assert_not_called()
    assert meta["advanced_last_month"] == "2026-09"


def test_advanced_cycle_sells_asset_below_sma_when_holding(monkeypatch):
    monkeypatch.setattr(bot.config, "LONG_TERM_AUTO_STRATEGY", "advanced")
    broker = MagicMock()
    broker.get_cash.return_value = 10_000.0
    broker.get_open_position.return_value = {"symbol": "X", "qty": 7.0, "avg_entry_price": 100.0, "current_price": 90.0}
    falling = _monthly_closes(list(range(130, 100, -1)))

    meta, p_get, p_set = _fake_state_meta()
    with p_get, p_set, \
         patch("bot.get_monthly_bars", return_value=falling), \
         patch("bot._last_close", return_value=100.0):
        bot.run_long_term_cycle(broker, execute=True, today=date(2026, 9, 2))

    assert broker.sell_market.call_count == len(bot.config.ADVANCED_TICKERS)
    assert all(c[0][1] == 7 for c in broker.sell_market.call_args_list)
    broker.buy_market.assert_not_called()


def test_advanced_cycle_runs_only_once_per_month(monkeypatch):
    monkeypatch.setattr(bot.config, "LONG_TERM_AUTO_STRATEGY", "advanced")
    broker = MagicMock()
    broker.get_cash.return_value = 10_000.0
    broker.get_open_position.return_value = None
    rising = _monthly_closes(list(range(100, 130)))

    meta, p_get, p_set = _fake_state_meta()
    with p_get, p_set, \
         patch("bot.get_monthly_bars", return_value=rising), \
         patch("bot._last_close", return_value=100.0):
        bot.run_long_term_cycle(broker, execute=True, today=date(2026, 9, 2))
        bot.run_long_term_cycle(broker, execute=True, today=date(2026, 9, 15))

    assert broker.buy_market.call_count == len(bot.config.ADVANCED_TICKERS)


def test_advanced_cycle_report_only_places_no_orders_and_does_not_consume_month(monkeypatch):
    monkeypatch.setattr(bot.config, "LONG_TERM_AUTO_STRATEGY", "advanced")
    broker = MagicMock()
    broker.get_cash.return_value = 10_000.0
    broker.get_open_position.return_value = None
    rising = _monthly_closes(list(range(100, 130)))

    meta, p_get, p_set = _fake_state_meta()
    with p_get, p_set, \
         patch("bot.get_monthly_bars", return_value=rising), \
         patch("bot._last_close", return_value=100.0):
        bot.run_long_term_cycle(broker, execute=False, today=date(2026, 9, 2))

    broker.buy_market.assert_not_called()
    assert "advanced_last_month" not in meta


def test_advanced_cycle_ignores_current_unclosed_month(monkeypatch):
    monkeypatch.setattr(bot.config, "LONG_TERM_AUTO_STRATEGY", "advanced")
    broker = MagicMock()
    broker.get_cash.return_value = 10_000.0
    broker.get_open_position.return_value = None
    values = list(range(130, 100, -1)) + [500.0]
    idx = pd.date_range("2024-03-31", periods=len(values), freq="ME")
    assert idx[-1].year == 2026 and idx[-1].month == 9
    bars = pd.DataFrame({"close": pd.Series(values, index=idx)})

    meta, p_get, p_set = _fake_state_meta()
    with p_get, p_set, \
         patch("bot.get_monthly_bars", return_value=bars), \
         patch("bot._last_close", return_value=100.0):
        bot.run_long_term_cycle(broker, execute=True, today=date(2026, 9, 2))

    broker.buy_market.assert_not_called()


def test_harry_browne_cycle_rebalances_when_due_and_skips_when_not(monkeypatch):
    monkeypatch.setattr(bot.config, "LONG_TERM_AUTO_STRATEGY", "harry_browne")
    monkeypatch.setattr(bot.config, "LONG_TERM_CAPITAL", 10_000.0)
    monkeypatch.setattr(bot.config, "REBALANCE_FREQUENCY", "quarterly")
    broker = MagicMock()
    broker.get_cash.return_value = 10_000.0
    broker.get_open_position.return_value = None

    meta, p_get, p_set = _fake_state_meta()
    with p_get, p_set, patch("bot._last_close", return_value=100.0):
        bot.run_long_term_cycle(broker, execute=True, today=date(2026, 1, 2))
        assert broker.buy_market.call_count == 4
        assert all(c[0][1] == 25 for c in broker.buy_market.call_args_list)
        assert meta["harry_browne_last_rebalance"] == "2026-01-02"

        bot.run_long_term_cycle(broker, execute=True, today=date(2026, 2, 15))
        assert broker.buy_market.call_count == 4

        bot.run_long_term_cycle(broker, execute=True, today=date(2026, 4, 1))
        assert broker.buy_market.call_count == 8


def test_long_term_cycle_none_does_nothing(monkeypatch):
    monkeypatch.setattr(bot.config, "LONG_TERM_AUTO_STRATEGY", "none")
    broker = MagicMock()

    bot.run_long_term_cycle(broker, execute=True, today=date(2026, 9, 2))

    broker.buy_market.assert_not_called()
    broker.sell_market.assert_not_called()


# --- Ciclo resistente alla mancanza di connessione -------------------------
# Regressione: bot lanciato subito dopo l'accensione del PC, connessione non
# ancora pronta -> ConnectTimeout -> l'intero giro del giorno perso (nessuna
# gestione delle posizioni aperte, nessun ordine nuovo).

def _connect_timeout():
    return requests.exceptions.ConnectTimeout("paper-api.alpaca.markets timed out")


def test_network_failure_is_recognised_through_the_cause_chain():
    try:
        try:
            raise _connect_timeout()
        except Exception as exc:
            raise RuntimeError("ciclo fallito") from exc
    except RuntimeError as wrapper:
        assert bot._is_network_failure(wrapper)


def test_api_error_is_not_treated_as_a_network_failure():
    from alpaca.common.exceptions import APIError

    assert not bot._is_network_failure(APIError("stop price must be greater than current price"))
    assert not bot._is_network_failure(ValueError("bug"))


def test_step_retries_while_the_broker_is_unreachable_then_succeeds():
    calls = []

    def run():
        calls.append(1)
        if len(calls) < 3:
            raise _connect_timeout()

    with patch.object(bot.time, "sleep") as slept:
        bot._run_step_with_retry("breve termine", run)

    assert len(calls) == 3
    assert [c.args[0] for c in slept.call_args_list] == list(bot.CYCLE_RETRY_WAITS[:2])


def test_step_gives_up_after_the_last_attempt_without_raising():
    calls = []

    def run():
        calls.append(1)
        raise _connect_timeout()

    with patch.object(bot.time, "sleep"), patch.object(bot.notify, "alert") as alert:
        bot._run_step_with_retry("breve termine", run)

    assert len(calls) == len(bot.CYCLE_RETRY_WAITS) + 1
    assert alert.called


def test_step_does_not_retry_a_non_network_failure():
    """Un ordine rifiutato o un bug non migliorano aspettando: riprovare
    ritarderebbe solo il resto del ciclo."""
    calls = []

    def run():
        calls.append(1)
        raise ValueError("bug")

    with patch.object(bot.time, "sleep") as slept, patch.object(bot.notify, "alert"):
        bot._run_step_with_retry("breve termine", run)

    assert len(calls) == 1
    assert not slept.called


def test_a_failing_short_term_step_still_lets_the_long_term_run():
    order = []
    with patch.object(bot, "cmd_short_term_once", side_effect=ValueError("bug")), \
         patch.object(bot, "cmd_long_term_once", side_effect=lambda a: order.append("lungo")), \
         patch.object(bot.notify, "alert"):
        bot._run_cycle_safely()
    assert order == ["lungo"]


def test_cycles_never_overlap():
    """Il giro iniziale e quello schedulato sono due job distinti: se il
    primo e' ancora in attesa di rete alle 16:15, farli partire insieme
    manderebbe ordini doppi."""
    reentered = []

    def run_short(_args):
        reentered.append(bot._run_cycle_safely())

    with patch.object(bot, "cmd_short_term_once", side_effect=run_short), \
         patch.object(bot, "cmd_long_term_once"), \
         patch.object(bot.log, "warning") as warned:
        bot._run_cycle_safely()

    assert warned.called
    assert bot._cycle_lock.acquire(blocking=False)
    bot._cycle_lock.release()


def test_schedule_registers_the_daily_job_before_running_the_first_cycle():
    """La rete assente puo' tenere il primo giro in attesa per minuti:
    l'appuntamento quotidiano deve essere gia' registrato, non dopo."""
    scheduler = MagicMock()
    with patch.object(bot, "BlockingScheduler", return_value=scheduler), \
         patch.object(bot.notify, "alert"):
        bot.cmd_schedule(argparse.Namespace())

    triggers = [c.args[1] if len(c.args) > 1 else None for c in scheduler.add_job.call_args_list]
    assert len(triggers) == 2
    assert isinstance(triggers[0], bot.CronTrigger)  # prima il quotidiano
    assert triggers[1] is None                       # poi il giro immediato
    assert scheduler.start.called
