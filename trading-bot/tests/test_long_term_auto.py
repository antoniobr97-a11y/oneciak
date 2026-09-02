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
