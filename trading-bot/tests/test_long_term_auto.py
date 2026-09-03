from datetime import date

import pandas as pd

from long_term import advanced_portfolio


def _monthly(values, start="2020-01-31"):
    idx = pd.date_range(start, periods=len(values), freq="ME")
    return pd.Series(values, index=idx)


def test_closed_monthly_closes_drops_current_month():
    s = _monthly([1, 2, 3], start="2026-07-31")  # lug, ago, set 2026
    out = advanced_portfolio.closed_monthly_closes(s, today=date(2026, 9, 2))
    assert list(out.values) == [1, 2]


def test_closed_monthly_closes_keeps_all_when_last_month_is_closed():
    s = _monthly([1, 2, 3], start="2026-06-30")  # giu, lug, ago 2026
    out = advanced_portfolio.closed_monthly_closes(s, today=date(2026, 9, 2))
    assert list(out.values) == [1, 2, 3]


def test_closed_monthly_closes_empty_series():
    s = pd.Series([], dtype=float)
    assert advanced_portfolio.closed_monthly_closes(s, today=date(2026, 9, 2)).empty


def test_is_above_sma_true_in_uptrend_false_in_downtrend():
    assert advanced_portfolio.is_above_sma(_monthly(list(range(100, 130))), sma_period=10) is True
    assert advanced_portfolio.is_above_sma(_monthly(list(range(130, 100, -1))), sma_period=10) is False


def test_is_above_sma_none_without_enough_history():
    assert advanced_portfolio.is_above_sma(_monthly([1, 2, 3]), sma_period=10) is None


def test_monthly_signal_on_closed_months_only():
    """Con il mese in corso incluso il segnale cambierebbe: qui i mesi
    chiusi sono piatti sotto la SMA (HOLD), il mese parziale spara in alto."""
    closed = [100.0] * 12 + [90.0]
    s = _monthly(closed + [500.0], start="2025-08-31")  # l'ultima barra = set 2026
    assert s.index[-1].month == 9 and s.index[-1].year == 2026
    clean = advanced_portfolio.closed_monthly_closes(s, today=date(2026, 9, 2))
    assert advanced_portfolio.monthly_signal(clean, sma_period=10).action != "BUY"


# --- Un ciclo fallito non deve essere segnato come completato ---------------
# Advanced agisce una volta al mese, Harry Browne una volta al trimestre: se
# un errore (rete, ordine rifiutato) lo marcasse comunque come fatto, il
# portafoglio resterebbe sbilanciato fino al periodo successivo senza che
# nessuno riprovi.

def test_advanced_month_is_not_marked_done_when_an_asset_fails(monkeypatch):
    import bot
    from unittest.mock import MagicMock, patch
    from datetime import date

    monkeypatch.setattr(bot.config, "LONG_TERM_AUTO_STRATEGY", "advanced")
    broker = MagicMock()
    broker.get_cash.return_value = 100_000.0
    broker.get_open_position.return_value = None
    broker.buy_market.side_effect = RuntimeError("rifiutato dal broker")

    import pandas as pd
    monthly = pd.Series(range(1, 40), dtype=float,
                        index=pd.date_range("2023-01-31", periods=39, freq="ME"))
    marked = {}
    with patch.object(bot, "get_monthly_bars", return_value=pd.DataFrame({"close": monthly})), \
         patch.object(bot, "_last_close", return_value=100.0), \
         patch.object(bot.position_state, "get_meta", return_value=None), \
         patch.object(bot.position_state, "set_meta", side_effect=lambda k, v: marked.update({k: v})), \
         patch.object(bot.notify, "alert"):
        bot.run_long_term_cycle(broker, execute=True, today=date(2026, 9, 3))

    assert marked == {}  # nulla segnato: si riprovera' domani


def test_harry_browne_rebalance_is_not_marked_done_when_an_etf_fails(monkeypatch):
    import bot
    from unittest.mock import MagicMock, patch
    from datetime import date

    monkeypatch.setattr(bot.config, "LONG_TERM_AUTO_STRATEGY", "harry_browne")
    broker = MagicMock()
    broker.get_cash.return_value = 100_000.0
    broker.get_open_position.return_value = None
    broker.buy_market.side_effect = RuntimeError("rifiutato dal broker")

    marked = {}
    with patch.object(bot, "_last_close", return_value=100.0), \
         patch.object(bot.position_state, "get_meta", return_value=None), \
         patch.object(bot.position_state, "set_meta", side_effect=lambda k, v: marked.update({k: v})), \
         patch.object(bot.notify, "alert"):
        bot.run_long_term_cycle(broker, execute=True, today=date(2026, 9, 3))

    assert marked == {}


def test_harry_browne_rebalance_is_marked_done_when_it_succeeds(monkeypatch):
    import bot
    from unittest.mock import MagicMock, patch
    from datetime import date

    monkeypatch.setattr(bot.config, "LONG_TERM_AUTO_STRATEGY", "harry_browne")
    broker = MagicMock()
    broker.get_cash.return_value = 100_000.0
    broker.get_open_position.return_value = None

    marked = {}
    with patch.object(bot, "_last_close", return_value=100.0), \
         patch.object(bot.position_state, "get_meta", return_value=None), \
         patch.object(bot.position_state, "set_meta", side_effect=lambda k, v: marked.update({k: v})), \
         patch.object(bot.notify, "alert"):
        bot.run_long_term_cycle(broker, execute=True, today=date(2026, 9, 3))

    assert marked["harry_browne_last_rebalance"] == "2026-09-03"
