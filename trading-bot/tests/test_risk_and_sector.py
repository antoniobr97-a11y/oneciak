"""Test della logica che decide gli avvisi di rischio e la conferma
settoriale (short_term/risk_checks.py, short_term/sector.py).

Questi due moduli erano coperti al 38% e 42%: oltre meta' del codice non
veniva mai eseguito da un test. Non e' un dettaglio -- il bug degli swing
point e' vissuto proprio qui, invisibile, perche' nessun test guardava
cosa quelle funzioni rispondessero davvero."""
import pandas as pd

from common import config
from short_term import risk_checks, sector


def _weekly(highs, lows=None, closes=None):
    n = len(highs)
    lows = lows if lows is not None else [h - 5 for h in highs]
    closes = closes if closes is not None else [(h + l) / 2 for h, l in zip(highs, lows)]
    return pd.DataFrame(
        {"open": closes, "high": highs, "low": lows, "close": closes, "volume": [1e6] * n},
        index=pd.date_range("2024-01-05", periods=n, freq="W-FRI"),
    )


# due massimi swing netti a 120 e 150, nient'altro sopra 100
HIGHS = [100, 101, 102, 120, 102, 101, 100, 101, 102, 150, 102, 101, 100]


# --- supporti / resistenze ---------------------------------------------------

def test_the_nearest_resistance_above_entry_is_the_one_that_counts():
    sr = risk_checks.support_resistance_check(_weekly(HIGHS), entry=100.0, risk_per_share=5.0, direction="long")
    assert sr.nearest_level == 120.0          # il piu' vicino sopra l'entrata, non il piu' alto
    assert sr.r_multiple_distance == 4.0      # (120-100)/5
    assert sr.too_close is False              # 4R > soglia di 3R


def test_a_resistance_within_three_r_is_flagged():
    sr = risk_checks.support_resistance_check(_weekly(HIGHS), entry=110.0, risk_per_share=5.0, direction="long")
    assert sr.r_multiple_distance == 2.0      # (120-110)/5
    assert sr.too_close is True


def test_no_resistance_above_entry_is_not_a_warning():
    sr = risk_checks.support_resistance_check(_weekly(HIGHS), entry=200.0, risk_per_share=5.0, direction="long")
    assert sr.nearest_level is None
    assert sr.too_close is False              # "non lo so" non deve diventare "pericolo"


def test_a_short_looks_for_support_below_the_entry():
    lows = [200 - h for h in HIGHS]           # specchio: minimi swing a 80 e 50
    df = _weekly([l + 5 for l in lows], lows=lows)
    sr = risk_checks.support_resistance_check(df, entry=100.0, risk_per_share=5.0, direction="short")
    assert sr.nearest_level == 80.0           # il piu' vicino SOTTO l'entrata
    assert sr.r_multiple_distance == 4.0


def test_zero_risk_per_share_is_not_analysed():
    sr = risk_checks.support_resistance_check(_weekly(HIGHS), entry=100.0, risk_per_share=0.0, direction="long")
    assert sr.nearest_level is None and sr.too_close is False


def test_the_threshold_comes_from_the_configuration(monkeypatch):
    monkeypatch.setattr(config, "SUPPORT_RESISTANCE_MIN_R_MULTIPLE", 5.0)
    sr = risk_checks.support_resistance_check(_weekly(HIGHS), entry=100.0, risk_per_share=5.0, direction="long")
    assert sr.r_multiple_distance == 4.0 and sr.too_close is True  # 4R ora e' sotto la soglia


# --- prezzo minimo per gli short ---------------------------------------------

def test_only_shorts_have_a_minimum_price(monkeypatch):
    monkeypatch.setattr(config, "SHORT_MIN_PRICE", 80.0)
    assert risk_checks.price_level_check(50.0, "short").blocks_trade is True
    assert risk_checks.price_level_check(90.0, "short").blocks_trade is False
    assert risk_checks.price_level_check(5.0, "long").blocks_trade is False


# --- trimestrali --------------------------------------------------------------

def test_missing_earnings_data_is_not_a_warning():
    check = risk_checks.EarningsCheck(None, None)
    assert check.warn is False                # dato mancante != pericolo


def test_earnings_within_the_window_are_flagged(monkeypatch):
    monkeypatch.setattr(config, "EARNINGS_WARNING_DAYS", 15)
    assert risk_checks.EarningsCheck(None, 3).warn is True
    assert risk_checks.EarningsCheck(None, 15).warn is True     # estremo incluso
    assert risk_checks.EarningsCheck(None, 16).warn is False
    assert risk_checks.EarningsCheck(None, -1).warn is False    # gia' passate


# --- forza relativa e conferma settoriale -------------------------------------

def _series(values):
    return pd.Series(values, dtype=float, index=pd.date_range("2025-01-01", periods=len(values), freq="B"))


def test_relative_strength_only_compares_overlapping_dates():
    a = _series([10, 20, 30, 40])
    b = _series([1, 2, 3, 4]).iloc[1:]        # parte un giorno dopo
    rs = sector.relative_strength(a, b)
    assert len(rs) == 3                        # solo le date in comune
    assert list(rs) == [10.0, 10.0, 10.0]


def test_rising_and_falling_look_at_the_window_ends():
    assert sector.is_rising(_series([1, 5, 2, 3]), lookback=4) is True    # 3 > 1
    assert sector.is_falling(_series([1, 5, 2, 3]), lookback=4) is False
    assert sector.is_falling(_series([9, 1, 8, 2]), lookback=4) is True   # 2 < 9
    assert sector.is_rising(_series([5, 5]), lookback=2) is False         # piatto non sale


def _rising(start, step, n=70):
    return pd.DataFrame({"close": [start + step * i for i in range(n)]},
                        index=pd.date_range("2025-01-01", periods=n, freq="B"))


def test_sector_confirmation_needs_every_condition_together():
    """`passes` richiede quattro condizioni allineate: titolo e settore
    nella stessa direzione, il titolo piu' forte del settore, il settore
    piu' forte sia dell'S&P500 sia del Russell."""
    stock = _rising(100, 1.0)      # il piu' forte
    sec = _rising(100, 0.5)        # sale, ma meno del titolo
    spy = _rising(100, 0.1)
    iwm = _rising(100, 0.1)

    ok = sector.sector_check(stock, sec, spy, iwm, "long", "XLK")
    assert ok.passes is True

    # se il settore e' piu' debole dell'indice, salta tutto
    weak = sector.sector_check(stock, _rising(100, 0.05), spy, iwm, "long", "XLK")
    assert weak.rs_sector_vs_sp500_ok is False and weak.passes is False

    # se il titolo e' piu' debole del proprio settore, salta tutto
    lagging = sector.sector_check(_rising(100, 0.2), sec, spy, iwm, "long", "XLK")
    assert lagging.rs_stock_vs_sector_ok is False and lagging.passes is False


def test_an_unknown_sector_never_confirms():
    stock = _rising(100, 1.0)
    analysis = sector.sector_check(stock, _rising(100, 0.5), _rising(100, 0.1), _rising(100, 0.1), "long", None)
    assert analysis.sector_etf is None
    assert analysis.passes is False           # senza settore non si conferma nulla


def test_a_falling_sector_does_not_confirm_a_long():
    stock = _rising(100, 1.0)
    falling = _rising(140, -0.5)
    analysis = sector.sector_check(stock, falling, _rising(100, 0.1), _rising(100, 0.1), "long", "XLK")
    assert analysis.same_direction is False and analysis.passes is False


# --- divergenza prezzo / MACD -------------------------------------------------
# La funzione confronta gli ULTIMI DUE massimi. Prima del raggruppamento dei
# punti di inversione, due barre adiacenti dello stesso picco comparivano
# entrambe nella lista: il confronto era fra un picco e SE STESSO (prezzo
# uguale, quindi mai una divergenza) e il controllo non serviva a niente.

def _weekly_from(closes):
    import numpy as np

    c = np.array(closes, dtype=float)
    return pd.DataFrame(
        {"open": c, "high": c + 1, "low": c - 1, "close": c, "volume": [1e6] * len(c)},
        index=pd.date_range("2022-01-07", periods=len(c), freq="W-FRI"),
    )


def _two_rallies(second_leg_bars):
    """Rally ripido, ritracciamento, poi risalita a un massimo piu' alto.
    Piu' lunga la seconda gamba, piu' debole il momentum che la accompagna."""
    import numpy as np

    return _weekly_from(
        list(np.linspace(100, 100, 30))
        + list(np.linspace(100, 160, 12))
        + list(np.linspace(160, 120, 10))
        + list(np.linspace(120, 162, second_leg_bars))
        + list(np.linspace(162, 155, 4))
    )


def test_a_higher_high_on_weaker_momentum_is_a_divergence():
    assert risk_checks.divergence_check(_two_rallies(40), "long").has_divergence is True


def test_a_higher_high_on_stronger_momentum_is_not_a_divergence():
    """Prima gamba LENTA, seconda RIPIDA: il prezzo fa un nuovo massimo e
    il momentum lo accompagna, quindi nessun avviso. (Il caso simmetrico
    del test precedente: li' la seconda gamba era la piu' debole.)"""
    import numpy as np

    df = _weekly_from(
        list(np.linspace(100, 100, 30))
        + list(np.linspace(100, 130, 30))   # salita lenta
        + list(np.linspace(130, 115, 8))
        + list(np.linspace(115, 140, 6))    # ripartenza ripida verso un massimo piu' alto
        + list(np.linspace(140, 134, 4))
    )
    assert risk_checks.divergence_check(df, "long").has_divergence is False


def test_the_last_two_swing_points_are_two_different_peaks():
    from short_term.indicators import swing_points

    df = _two_rallies(40)
    peaks = swing_points(df["high"], order=2, kind="high")
    (i1, p1), (i2, p2) = peaks[-2], peaks[-1]
    assert i2 - i1 > 2      # non due barre della stessa inversione
    assert p2 != p1         # e nemmeno lo stesso prezzo confrontato con se stesso


def test_too_few_swing_points_is_not_a_divergence():
    import numpy as np

    flat = _weekly_from(list(np.linspace(100, 140, 50)))  # salita pulita, nessuna inversione
    assert risk_checks.divergence_check(flat, "long").has_divergence is False
