"""Test della logica di orchestrazione in bot.py con Broker e screener
mockati -- nessuna chiamata di rete, nessun ordine reale."""
import argparse
from unittest.mock import MagicMock, patch

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


# --- manage_open_short_term_positions --------------------------------------

def test_manage_positions_takes_partial_at_1r_and_moves_stop_to_breakeven():
    broker = MagicMock()
    # long: entrata 100, stop 95 (rischio 5) -> 1R = 105
    broker.list_open_positions.return_value = [_position("AAPL", 10, 100.0, 106.0)]
    broker.get_open_stop_order.return_value = _stop_order(95.0)

    bot.manage_open_short_term_positions(broker)

    broker.close_partial.assert_called_once_with("AAPL", 5, "long")
    broker.move_stop_to_breakeven.assert_called_once_with("AAPL", 5, 100.0, "long")


def test_manage_positions_no_action_below_1r():
    broker = MagicMock()
    broker.list_open_positions.return_value = [_position("AAPL", 10, 100.0, 102.0)]  # sotto 1R (105)
    broker.get_open_stop_order.return_value = _stop_order(95.0)

    bot.manage_open_short_term_positions(broker)

    broker.close_partial.assert_not_called()
    broker.move_stop_to_breakeven.assert_not_called()


def test_manage_positions_skips_already_at_breakeven():
    broker = MagicMock()
    # stop già uguale all'entrata -> metà posizione già gestita in un ciclo precedente
    broker.list_open_positions.return_value = [_position("AAPL", 5, 100.0, 120.0)]
    broker.get_open_stop_order.return_value = _stop_order(100.0)

    bot.manage_open_short_term_positions(broker)

    broker.close_partial.assert_not_called()
    broker.move_stop_to_breakeven.assert_not_called()


def test_manage_positions_short_direction_1r_math():
    broker = MagicMock()
    # short: entrata 100, stop 105 (rischio 5) -> 1R = 95
    broker.list_open_positions.return_value = [_position("TSLA", -10, 100.0, 94.0)]
    broker.get_open_stop_order.return_value = _stop_order(105.0)

    bot.manage_open_short_term_positions(broker)

    broker.close_partial.assert_called_once_with("TSLA", 5, "short")
    broker.move_stop_to_breakeven.assert_called_once_with("TSLA", 5, 100.0, "short")


def test_manage_positions_odd_qty_moves_full_stop_without_partial():
    broker = MagicMock()
    # 1 sola azione: non divisibile, ma lo stop deve comunque andare a pareggio
    broker.list_open_positions.return_value = [_position("AAPL", 1, 100.0, 106.0)]
    broker.get_open_stop_order.return_value = _stop_order(95.0)

    bot.manage_open_short_term_positions(broker)

    broker.close_partial.assert_not_called()
    broker.move_stop_to_breakeven.assert_called_once_with("AAPL", 1, 100.0, "long")


def test_manage_positions_no_stop_order_is_skipped_safely():
    broker = MagicMock()
    broker.list_open_positions.return_value = [_position("AAPL", 10, 100.0, 200.0)]
    broker.get_open_stop_order.return_value = None

    bot.manage_open_short_term_positions(broker)  # non deve sollevare eccezioni

    broker.close_partial.assert_not_called()
    broker.move_stop_to_breakeven.assert_not_called()


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
         patch("bot._print_candidate"):
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
         patch("bot._print_candidate"):
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
