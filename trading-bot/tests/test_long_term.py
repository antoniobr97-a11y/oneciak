from datetime import date

import pandas as pd

from long_term import advanced_portfolio, harry_browne, pac, risk_profile


def test_harry_browne_target_shares_25_pct_each():
    prices = {"VT": 100.0, "TLT": 90.0, "SHY": 80.0, "GLD": 180.0}
    shares = harry_browne.target_shares(10_000, prices, tickers=list(prices))
    assert shares == {"VT": 25, "TLT": 27, "SHY": 31, "GLD": 13}
    for ticker, qty in shares.items():
        assert qty * prices[ticker] <= 2_500 + 1e-9


def test_harry_browne_rebalance_orders_buy_and_sell():
    prices = {"VT": 100.0, "TLT": 90.0, "SHY": 80.0, "GLD": 180.0}
    current = {"VT": 40, "TLT": 0, "SHY": 31, "GLD": 13}  # VT overweight, TLT underweight
    orders = harry_browne.rebalance_orders(current, prices, 10_000, tickers=list(prices))
    assert orders["VT"] < 0  # sell some VT
    assert orders["TLT"] > 0  # buy TLT
    assert orders["SHY"] == 0
    assert orders["GLD"] == 0


def test_harry_browne_rebalance_due():
    assert harry_browne.is_rebalance_due(date(2026, 1, 1), date(2026, 4, 2), "quarterly")
    assert not harry_browne.is_rebalance_due(date(2026, 1, 1), date(2026, 3, 1), "quarterly")


def test_risk_profile_classify_bands():
    assert risk_profile.classify(10).profile == "molto_basso"
    assert risk_profile.classify(20).profile == "basso"
    assert risk_profile.classify(25).profile == "medio"
    assert risk_profile.classify(30).profile == "alto"
    assert risk_profile.classify(40).profile == "molto_alto"


def test_risk_profile_weights_sum_to_100():
    for score in (10, 20, 25, 30, 40):
        w = risk_profile.classify(score)
        assert abs(sum(w.as_dict().values()) - 100.0) < 1e-9


def test_advanced_target_weights_split_bond_bucket():
    expected_bond = risk_profile.classify(25).bond / 100  # "medio" tier, normalized
    weights = risk_profile.advanced_target_weights(score=25)
    assert abs(weights["bond_long"] - weights["bond_short"]) < 1e-9
    assert abs((weights["bond_long"] + weights["bond_short"]) - expected_bond) < 1e-9
    assert abs(sum(weights.values()) - 1.0) < 1e-9


def _monthly_series(values):
    idx = pd.date_range("2020-01-31", periods=len(values), freq="ME")
    return pd.Series(values, index=idx, dtype=float)


def test_advanced_monthly_signal_buy_on_clean_upward_cross():
    # Mild decline (close stays below its own trailing SMA10), then a clean
    # jump above the SMA on the last month.
    decline = [100 - i * 0.05 for i in range(11)]
    closes = _monthly_series(decline + [115])
    signal = advanced_portfolio.monthly_signal(closes, sma_period=10)
    assert signal.action == "BUY"


def test_advanced_monthly_signal_hold_without_clean_cross():
    closes = _monthly_series([100 + i * 0.1 for i in range(12)])
    signal = advanced_portfolio.monthly_signal(closes, sma_period=10)
    assert signal.action == "HOLD"


def test_pac_never_sells_only_buys_underweight():
    current_value = {"equity": 1000.0, "bond": 100.0, "gold": 100.0}
    target_weights = {"equity": 0.5, "bond": 0.25, "gold": 0.25}
    prices = {"equity": 100.0, "bond": 50.0, "gold": 200.0}
    orders = pac.pac_buy_orders(300.0, current_value, target_weights, prices)
    assert all(qty >= 0 for qty in orders.values())
    assert orders["bond"] > 0  # most underweight vs target -> gets funded first


def test_pac_average_cost_basis_updates():
    pos = pac.CostBasis(avg_cost=100.0, qty=10)
    updated = pac.update_average_cost(pos, buy_qty=10, buy_price=80.0)
    assert updated.qty == 20
    assert abs(updated.avg_cost - 90.0) < 1e-9
