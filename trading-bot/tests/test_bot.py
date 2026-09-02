"""Test della logica di orchestrazione in bot.py con Broker e screener
mockati -- nessuna chiamata di rete, nessun ordine reale."""
import argparse
from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

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


def test_short_term_equity_excludes_long_term_etf_value():
    broker = MagicMock()
    etf = bot.config.HARRY_BROWNE_TICKERS[0]
    broker.get_equity.return_value = 10_000.0
    broker.list_open_positions.return_value = [_position(etf, 10, 100.0, 300.0)]

    assert bot._short_term_equity(broker) == 7_000.0


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
    broker.get_equity.return_value = equity
    broker.get_cash.return_value = cash
    return broker


def test_cmd_short_term_once_submits_stop_entries_and_stops_at_aggregate_risk_cap():
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


def test_cmd_short_term_once_market_closed_does_nothing():
    broker = MagicMock()
    broker.is_market_open.return_value = False

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe") as mock_screen:
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    mock_screen.assert_not_called()
    broker.list_open_positions.assert_not_called()


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


def test_short_term_position_count_excludes_long_term_etfs():
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
         _patched_state({"AAPL": ENTERED_10}, meta={"equity_peak": 10_000.0}) as state:
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    broker.submit_stop_entry.assert_not_called()  # niente nuove entrate
    broker.submit_oco_exit.assert_called_once()  # ma la posizione aperta e' stata gestita
    assert state.meta["equity_peak"] == 10_000.0


def test_drawdown_brake_updates_peak_and_allows_entries_within_limit(monkeypatch):
    monkeypatch.setattr(bot.config, "SHORT_TERM_MAX_DRAWDOWN_PCT", 15.0)
    broker = _cycle_broker(equity=12_000.0)

    with patch("bot.Broker", return_value=broker), \
         patch("bot.screen_universe", return_value=[_candidate("MSFT")]), \
         patch("bot._print_candidate"), \
         _patched_state(meta={"equity_peak": 10_000.0}) as state:
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    broker.submit_stop_entry.assert_called_once()
    assert state.meta["equity_peak"] == 12_000.0


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
