"""Test della logica di orchestrazione in bot.py con Broker e screener
mockati -- nessuna chiamata di rete, nessun ordine reale."""
import argparse
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pandas as pd

import bot
from short_term import levels as levels_mod
from short_term.patterns import PatternMatch
from short_term.screener import Candidate
from short_term.trend import TrendQualification


def _position(symbol, qty, entry_price, current_price):
    return {"symbol": symbol, "qty": qty, "avg_entry_price": entry_price, "current_price": current_price}


def _stop_order(stop_price):
    order = MagicMock()
    order.stop_price = stop_price
    return order


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

    def __init__(self, initial=None):
        self.data = {k: dict(v) for k, v in (initial or {}).items()}

    def get(self, symbol):
        return self.data.get(symbol, {})

    def set_fields(self, symbol, **fields):
        self.data.setdefault(symbol, {}).update(fields)

    def clear(self, symbol):
        self.data.pop(symbol, None)

    def tracked_symbols(self):
        return list(self.data.keys())


@contextmanager
def _patched_state(initial=None):
    fake = _FakeState(initial)
    with patch("bot.position_state.get", side_effect=fake.get), \
         patch("bot.position_state.set_fields", side_effect=fake.set_fields), \
         patch("bot.position_state.clear", side_effect=fake.clear), \
         patch("bot.position_state.tracked_symbols", side_effect=fake.tracked_symbols):
        yield fake


# --- manage_open_short_term_positions: stadio 1R -----------------------------

def test_manage_positions_1r_stage_triggers_partial_and_breakeven():
    broker = MagicMock()
    # long: entrata 100, rischio 5 (stato) -> 1R = 105
    broker.list_open_positions.return_value = [_position("AAPL", 10, 100.0, 106.0)]

    with _patched_state({"AAPL": {"risk_per_share": 5.0, "original_qty": 10, "stage": "entered"}}) as state:
        bot.manage_open_short_term_positions(broker)

    broker.close_partial.assert_called_once_with("AAPL", 5, "long")
    broker.move_stop_to_breakeven.assert_called_once_with("AAPL", 5, 100.0, "long")
    assert state.data["AAPL"]["stage"] == "1R_done"


def test_manage_positions_no_action_below_1r():
    broker = MagicMock()
    broker.list_open_positions.return_value = [_position("AAPL", 10, 100.0, 102.0)]  # sotto 1R (105)

    with _patched_state({"AAPL": {"risk_per_share": 5.0, "original_qty": 10, "stage": "entered"}}):
        bot.manage_open_short_term_positions(broker)

    broker.close_partial.assert_not_called()
    broker.move_stop_to_breakeven.assert_not_called()


def test_manage_positions_short_1r_math():
    broker = MagicMock()
    # short: entrata 100, rischio 5 -> 1R = 95
    broker.list_open_positions.return_value = [_position("TSLA", -10, 100.0, 94.0)]

    with _patched_state({"TSLA": {"risk_per_share": 5.0, "original_qty": 10, "stage": "entered"}}):
        bot.manage_open_short_term_positions(broker)

    broker.close_partial.assert_called_once_with("TSLA", 5, "short")
    broker.move_stop_to_breakeven.assert_called_once_with("TSLA", 5, 100.0, "short")


def test_manage_positions_odd_qty_1r_moves_full_stop_without_partial():
    broker = MagicMock()
    broker.list_open_positions.return_value = [_position("AAPL", 1, 100.0, 106.0)]

    with _patched_state({"AAPL": {"risk_per_share": 5.0, "original_qty": 1, "stage": "entered"}}):
        bot.manage_open_short_term_positions(broker)

    broker.close_partial.assert_not_called()
    broker.move_stop_to_breakeven.assert_called_once_with("AAPL", 1, 100.0, "long")


def test_manage_positions_no_saved_state_is_skipped_safely():
    broker = MagicMock()
    broker.list_open_positions.return_value = [_position("AAPL", 10, 100.0, 200.0)]

    with _patched_state({}):  # nessuno stato salvato per AAPL
        bot.manage_open_short_term_positions(broker)  # non deve sollevare eccezioni

    broker.close_partial.assert_not_called()
    broker.move_stop_to_breakeven.assert_not_called()


# --- manage_open_short_term_positions: stadio 3R e runner -------------------

def test_manage_positions_3r_stage_triggers_second_partial():
    broker = MagicMock()
    # dopo il 1R restano 5 azioni (meta' delle 10 originali); a 3R (115) si
    # vende un'altra quota pari al 30% dell'originale (3), lasciando un
    # "runner" di 2 (20% di 10).
    broker.list_open_positions.return_value = [_position("AAPL", 5, 100.0, 116.0)]

    with _patched_state({"AAPL": {"risk_per_share": 5.0, "original_qty": 10, "stage": "1R_done"}}) as state:
        bot.manage_open_short_term_positions(broker)

    broker.close_partial.assert_called_once_with("AAPL", 3, "long")
    assert state.data["AAPL"]["stage"] == "3R_done"


def test_manage_positions_no_action_between_1r_and_3r():
    broker = MagicMock()
    broker.list_open_positions.return_value = [_position("AAPL", 5, 100.0, 108.0)]  # sotto 3R (115)

    with _patched_state({"AAPL": {"risk_per_share": 5.0, "original_qty": 10, "stage": "1R_done"}}):
        bot.manage_open_short_term_positions(broker)

    broker.close_partial.assert_not_called()


def test_manage_positions_runner_exits_on_long_term_ma_reversal():
    broker = MagicMock()
    broker.list_open_positions.return_value = [_position("AAPL", 2, 100.0, 130.0)]

    # SMA200 crescente e ben sopra l'ultima chiusura -> inversione rilevata
    closes = pd.Series(list(range(100, 300)))  # 200 barre, ultima chiusura 299 (piu' bassa della SMA finale ~200)
    bars = pd.DataFrame({"close": closes[::-1].reset_index(drop=True)})  # trend discendente -> chiusura sotto SMA200

    with _patched_state({"AAPL": {"risk_per_share": 5.0, "original_qty": 10, "stage": "3R_done"}}) as state, \
         patch("bot.get_daily_bars", return_value=bars):
        bot.manage_open_short_term_positions(broker)

    broker.flatten.assert_called_once_with("AAPL")
    assert "AAPL" not in state.data


def test_manage_positions_runner_holds_without_ma_reversal():
    broker = MagicMock()
    broker.list_open_positions.return_value = [_position("AAPL", 2, 100.0, 130.0)]

    closes = pd.Series(list(range(100, 300)))  # trend salente -> chiusura sopra SMA200
    bars = pd.DataFrame({"close": closes})

    with _patched_state({"AAPL": {"risk_per_share": 5.0, "original_qty": 10, "stage": "3R_done"}}), \
         patch("bot.get_daily_bars", return_value=bars):
        bot.manage_open_short_term_positions(broker)

    broker.flatten.assert_not_called()


def test_manage_positions_clears_orphaned_state_for_closed_positions():
    broker = MagicMock()
    broker.list_open_positions.return_value = []  # posizione chiusa dallo stop del broker

    with _patched_state({"OLDSYM": {"risk_per_share": 5.0, "original_qty": 10, "stage": "1R_done"}}) as state:
        bot.manage_open_short_term_positions(broker)

    assert "OLDSYM" not in state.data


# --- cmd_short_term_once: tetto di rischio aggregato + posizioni duplicate --

def test_cmd_short_term_once_stops_at_aggregate_risk_cap():
    candidates = [_candidate(f"SYM{i}") for i in range(20)]  # ben oltre il tetto (12% / 1% = 12)

    mock_broker_instance = MagicMock()
    mock_broker_instance.is_market_open.return_value = True
    mock_broker_instance.list_open_positions.return_value = []
    mock_broker_instance.get_equity.return_value = 10_000.0
    mock_broker_instance.get_open_position.return_value = None

    with patch("bot.Broker", return_value=mock_broker_instance), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"), \
         patch("bot.position_state.set_fields"):
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    # con rischio 1%/trade e tetto 12%, si aprono al massimo 12 posizioni
    assert mock_broker_instance.enter_with_stop.call_count == 12


def test_cmd_short_term_once_skips_symbol_already_in_position():
    candidates = [_candidate("AAPL"), _candidate("MSFT")]

    mock_broker_instance = MagicMock()
    mock_broker_instance.is_market_open.return_value = True
    mock_broker_instance.list_open_positions.return_value = []
    mock_broker_instance.get_equity.return_value = 10_000.0
    mock_broker_instance.get_open_position.side_effect = lambda s: {"symbol": "AAPL"} if s == "AAPL" else None

    with patch("bot.Broker", return_value=mock_broker_instance), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"), \
         patch("bot.position_state.set_fields"):
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    mock_broker_instance.enter_with_stop.assert_called_once()
    called_symbol = mock_broker_instance.enter_with_stop.call_args[0][0]
    assert called_symbol == "MSFT"


def test_cmd_short_term_once_market_closed_does_nothing():
    mock_broker_instance = MagicMock()
    mock_broker_instance.is_market_open.return_value = False

    with patch("bot.Broker", return_value=mock_broker_instance), \
         patch("bot.screen_universe") as mock_screen:
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    mock_screen.assert_not_called()
    mock_broker_instance.list_open_positions.assert_not_called()


def test_cmd_short_term_once_report_only_never_calls_enter_with_stop():
    candidates = [_candidate("AAPL"), _candidate("MSFT")]

    mock_broker_instance = MagicMock()
    mock_broker_instance.is_market_open.return_value = True
    mock_broker_instance.list_open_positions.return_value = []
    mock_broker_instance.get_equity.return_value = 10_000.0
    mock_broker_instance.get_open_position.return_value = None

    with patch("bot.Broker", return_value=mock_broker_instance), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"):
        bot.cmd_short_term_once(argparse.Namespace(execute=False))

    mock_broker_instance.enter_with_stop.assert_not_called()


# --- isolamento errori: un simbolo che fallisce non blocca gli altri ------

def test_manage_positions_one_symbol_error_does_not_block_others():
    broker = MagicMock()
    broker.list_open_positions.return_value = [
        _position("BAD", 10, 100.0, 106.0),
        _position("AAPL", 10, 100.0, 106.0),
    ]

    def _get(symbol):
        if symbol == "BAD":
            raise ConnectionError("rete giu'")
        return {"risk_per_share": 5.0, "original_qty": 10, "stage": "entered"}

    with patch("bot.position_state.get", side_effect=_get), \
         patch("bot.position_state.set_fields"), \
         patch("bot.position_state.clear"), \
         patch("bot.position_state.tracked_symbols", return_value=["BAD", "AAPL"]):
        bot.manage_open_short_term_positions(broker)  # non deve sollevare eccezioni

    # AAPL, processato dopo il simbolo che fallisce, viene comunque gestito
    broker.close_partial.assert_called_once_with("AAPL", 5, "long")
    broker.move_stop_to_breakeven.assert_called_once_with("AAPL", 5, 100.0, "long")


def test_cmd_short_term_once_failed_order_does_not_block_next_candidate_or_count_toward_cap():
    candidates = [_candidate("BAD"), _candidate("MSFT")]

    mock_broker_instance = MagicMock()
    mock_broker_instance.is_market_open.return_value = True
    mock_broker_instance.list_open_positions.return_value = []
    mock_broker_instance.get_equity.return_value = 10_000.0
    mock_broker_instance.get_open_position.return_value = None
    mock_broker_instance.enter_with_stop.side_effect = [ConnectionError("ordine rifiutato"), None]

    with patch("bot.Broker", return_value=mock_broker_instance), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"), \
         patch("bot.position_state.set_fields"):
        bot.cmd_short_term_once(argparse.Namespace(execute=True))  # non deve sollevare eccezioni

    assert mock_broker_instance.enter_with_stop.call_count == 2
    second_call_symbol = mock_broker_instance.enter_with_stop.call_args_list[1][0][0]
    assert second_call_symbol == "MSFT"
