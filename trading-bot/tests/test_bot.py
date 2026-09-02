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
    # lo stop a pareggio va riemesso sul NUOVO residuo (5 - 3 = 2): quello
    # precedente viene cancellato da close_partial e copriva 5 azioni
    broker.move_stop_to_breakeven.assert_called_once_with("AAPL", 2, 100.0, "long")
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
    mock_broker_instance.get_cash.return_value = 1_000_000.0
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
    mock_broker_instance.get_cash.return_value = 1_000_000.0
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
    mock_broker_instance.get_cash.return_value = 1_000_000.0
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
    mock_broker_instance.get_cash.return_value = 1_000_000.0
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


# --- audit: auto-riparazione dello stop mancante ------------------------------

def test_missing_stop_is_replaced_at_original_level_before_1r():
    broker = MagicMock()
    broker.list_open_positions.return_value = [_position("AAPL", 10, 100.0, 102.0)]  # sotto 1R
    broker.get_open_stop_order.return_value = None  # nessuno stop attivo al broker

    with _patched_state({"AAPL": {"risk_per_share": 5.0, "original_qty": 10, "stage": "entered", "stop_price": 95.0}}):
        bot.manage_open_short_term_positions(broker)

    broker.place_stop.assert_called_once_with("AAPL", 10, 95.0, "long")


def test_missing_stop_is_replaced_at_breakeven_after_1r():
    broker = MagicMock()
    broker.list_open_positions.return_value = [_position("AAPL", 5, 100.0, 108.0)]  # tra 1R e 3R
    broker.get_open_stop_order.return_value = None

    with _patched_state({"AAPL": {"risk_per_share": 5.0, "original_qty": 10, "stage": "1R_done", "stop_price": 95.0}}):
        bot.manage_open_short_term_positions(broker)

    broker.place_stop.assert_called_once_with("AAPL", 5, 100.0, "long")


def test_missing_stop_without_saved_level_alerts_and_does_not_invent_one():
    broker = MagicMock()
    broker.list_open_positions.return_value = [_position("AAPL", 10, 100.0, 102.0)]
    broker.get_open_stop_order.return_value = None

    with _patched_state({"AAPL": {"risk_per_share": 5.0, "original_qty": 10, "stage": "entered"}}), \
         patch("bot.notify.alert") as alert:
        bot.manage_open_short_term_positions(broker)

    broker.place_stop.assert_not_called()
    assert any(kw.get("level") == "error" for _, kw in alert.call_args_list)


def test_existing_stop_is_left_alone():
    broker = MagicMock()
    broker.list_open_positions.return_value = [_position("AAPL", 10, 100.0, 102.0)]
    broker.get_open_stop_order.return_value = _stop_order(95.0)

    with _patched_state({"AAPL": {"risk_per_share": 5.0, "original_qty": 10, "stage": "entered", "stop_price": 95.0}}):
        bot.manage_open_short_term_positions(broker)

    broker.place_stop.assert_not_called()


# --- audit: separazione breve/lungo termine nello stesso conto ---------------

def test_long_term_etfs_are_ignored_by_short_term_management():
    broker = MagicMock()
    etf = bot.config.ADVANCED_TICKERS[0]
    broker.list_open_positions.return_value = [_position(etf, 10, 100.0, 200.0)]  # +100%, ma e' un ETF di lungo termine
    broker.get_open_stop_order.return_value = None

    with _patched_state({}):
        bot.manage_open_short_term_positions(broker)

    broker.close_partial.assert_not_called()
    broker.place_stop.assert_not_called()


def test_short_term_equity_excludes_long_term_etf_value():
    broker = MagicMock()
    etf = bot.config.HARRY_BROWNE_TICKERS[0]
    broker.get_equity.return_value = 10_000.0
    broker.list_open_positions.return_value = [_position(etf, 10, 100.0, 300.0)]  # 3.000$ di ETF

    assert bot._short_term_equity(broker) == 7_000.0


def test_short_term_position_count_excludes_long_term_etfs():
    candidates = [_candidate(f"SYM{i}") for i in range(20)]
    etf = bot.config.ADVANCED_TICKERS[0]

    mock_broker_instance = MagicMock()
    mock_broker_instance.is_market_open.return_value = True
    # 11 ETF di lungo termine aperti: NON devono contare nel tetto (12 posizioni)
    mock_broker_instance.list_open_positions.return_value = [_position(f"{etf}", 1, 1.0, 1.0)] * 11
    mock_broker_instance.get_equity.return_value = 10_000.0
    mock_broker_instance.get_cash.return_value = 1_000_000.0
    mock_broker_instance.get_open_position.return_value = None

    with patch("bot.Broker", return_value=mock_broker_instance), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"), \
         patch("bot.position_state.set_fields"), \
         patch("bot.position_state.get", return_value={}), \
         patch("bot.position_state.tracked_symbols", return_value=[]):
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    assert mock_broker_instance.enter_with_stop.call_count == 12


# --- audit: tetto di cassa (nessuna leva) ------------------------------------

def test_cash_cap_limits_position_size_and_is_consumed_across_candidates():
    candidates = [_candidate("AAA", entry=100.0, stop=95.0, qty=10), _candidate("BBB", entry=100.0, stop=95.0, qty=10)]

    mock_broker_instance = MagicMock()
    mock_broker_instance.is_market_open.return_value = True
    mock_broker_instance.list_open_positions.return_value = []
    mock_broker_instance.get_equity.return_value = 10_000.0
    mock_broker_instance.get_cash.return_value = 1_500.0  # basta per 10 azioni della prima e 5 della seconda
    mock_broker_instance.get_open_position.return_value = None

    with patch("bot.Broker", return_value=mock_broker_instance), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"), \
         patch("bot.position_state.set_fields") as set_fields:
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    calls = mock_broker_instance.enter_with_stop.call_args_list
    assert [(c[0][0], c[0][1]) for c in calls] == [("AAA", 10), ("BBB", 5)]
    # lo stato salva la size EFFETTIVA e il livello di stop per l'auto-riparazione
    saved = {c[0][0]: c[1] for c in set_fields.call_args_list}
    assert saved["BBB"]["original_qty"] == 5
    assert saved["BBB"]["stop_price"] == 95.0


def test_cash_cap_skips_candidate_when_not_even_one_share_is_affordable():
    candidates = [_candidate("AAA", entry=100.0, stop=95.0, qty=10)]

    mock_broker_instance = MagicMock()
    mock_broker_instance.is_market_open.return_value = True
    mock_broker_instance.list_open_positions.return_value = []
    mock_broker_instance.get_equity.return_value = 10_000.0
    mock_broker_instance.get_cash.return_value = 50.0
    mock_broker_instance.get_open_position.return_value = None

    with patch("bot.Broker", return_value=mock_broker_instance), \
         patch("bot.screen_universe", return_value=candidates), \
         patch("bot._print_candidate"), \
         patch("bot.position_state.set_fields"):
        bot.cmd_short_term_once(argparse.Namespace(execute=True))

    mock_broker_instance.enter_with_stop.assert_not_called()


# --- audit: ciclo automatico di lungo termine ---------------------------------

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
    broker.get_open_position.return_value = None  # non in posizione su nessun ETF
    rising = _monthly_closes(list(range(100, 130)))  # sopra la SMA10

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
    falling = _monthly_closes(list(range(130, 100, -1)))  # sotto la SMA10

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
        bot.run_long_term_cycle(broker, execute=True, today=date(2026, 9, 15))  # stesso mese: niente

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
    """L'ultima barra mensile e' il mese in corso (settembre 2026): va
    scartata. Qui i mesi CHIUSI sono in discesa (fuori), mentre il mese
    in corso parziale spara in alto -- senza la correzione il bot
    comprerebbe su una barra incompleta."""
    monkeypatch.setattr(bot.config, "LONG_TERM_AUTO_STRATEGY", "advanced")
    broker = MagicMock()
    broker.get_cash.return_value = 10_000.0
    broker.get_open_position.return_value = None
    values = list(range(130, 100, -1)) + [500.0]
    idx = pd.date_range("2024-03-31", periods=len(values), freq="ME")  # l'ultima cade nel 2026-09
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
    broker.get_open_position.return_value = None  # partenza da zero: 4 acquisti da 25%

    meta, p_get, p_set = _fake_state_meta()
    with p_get, p_set, patch("bot._last_close", return_value=100.0):
        bot.run_long_term_cycle(broker, execute=True, today=date(2026, 1, 2))
        assert broker.buy_market.call_count == 4
        assert all(c[0][1] == 25 for c in broker.buy_market.call_args_list)  # 2.500$ / 100$
        assert meta["harry_browne_last_rebalance"] == "2026-01-02"

        bot.run_long_term_cycle(broker, execute=True, today=date(2026, 2, 15))  # non ancora dovuto
        assert broker.buy_market.call_count == 4

        bot.run_long_term_cycle(broker, execute=True, today=date(2026, 4, 1))  # trimestre passato
        assert broker.buy_market.call_count == 8


def test_long_term_cycle_none_does_nothing(monkeypatch):
    monkeypatch.setattr(bot.config, "LONG_TERM_AUTO_STRATEGY", "none")
    broker = MagicMock()

    bot.run_long_term_cycle(broker, execute=True, today=date(2026, 9, 2))

    broker.buy_market.assert_not_called()
    broker.sell_market.assert_not_called()
