"""Cache di anagrafica (settore, trimestrali) e i due bug che il suo
inserimento ha portato a galla in risk_checks.earnings_check."""
from datetime import date, timedelta

import pandas as pd
import pytest

from common import symbol_cache
from short_term import risk_checks, sector

TODAY = date(2026, 9, 8)


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Ogni test parte da una cache vuota, su un file tutto suo: la suite
    non deve mai leggere o scrivere la cache vera del bot."""
    monkeypatch.setattr(symbol_cache, "CACHE_PATH", str(tmp_path / "symbols.json"))
    symbol_cache.reset()
    yield
    symbol_cache.reset()


# --- la cache in se' ----------------------------------------------------------

def test_a_value_survives_a_flush_and_a_reload():
    symbol_cache.put("AAPL", "sector_etf", "XLK", TODAY)
    symbol_cache.flush()
    symbol_cache.reset()          # come un nuovo avvio del bot

    assert symbol_cache.get("AAPL", "sector_etf", TODAY, ttl_days=30) == "XLK"


def test_none_is_a_real_answer_and_is_cached():
    """"Yahoo non conosce il settore di questo titolo" e' una risposta: se
    non la si mettesse in cache, ogni sera si ripagherebbe la chiamata piu'
    lenta della scansione per riottenere lo stesso nulla."""
    symbol_cache.put("XYZ", "sector_etf", None, TODAY)

    assert symbol_cache.get("XYZ", "sector_etf", TODAY, ttl_days=30) is None
    assert symbol_cache.get("XYZ", "sector_etf", TODAY, ttl_days=30) is not symbol_cache.MISSING


def test_an_expired_value_is_ignored():
    symbol_cache.put("AAPL", "sector_etf", "XLK", TODAY - timedelta(days=31))

    assert symbol_cache.get("AAPL", "sector_etf", TODAY, ttl_days=30) is symbol_cache.MISSING


def test_a_value_dated_in_the_future_is_thrown_away():
    # orologio del PC spostato indietro: una voce "di domani" non deve
    # restare valida per sempre
    symbol_cache.put("AAPL", "sector_etf", "XLK", TODAY + timedelta(days=5))

    assert symbol_cache.get("AAPL", "sector_etf", TODAY, ttl_days=30) is symbol_cache.MISSING


def test_a_corrupt_cache_file_is_not_fatal(tmp_path, monkeypatch):
    path = tmp_path / "rotta.json"
    path.write_text("{questo non e' json")
    monkeypatch.setattr(symbol_cache, "CACHE_PATH", str(path))
    symbol_cache.reset()

    assert symbol_cache.get("AAPL", "sector_etf", TODAY, ttl_days=30) is symbol_cache.MISSING


def test_an_unwritable_cache_does_not_raise(monkeypatch):
    monkeypatch.setattr(symbol_cache, "CACHE_PATH", "/proc/non/esiste/symbols.json")
    symbol_cache.reset()
    symbol_cache.put("AAPL", "sector_etf", "XLK", TODAY)

    symbol_cache.flush()   # non deve sollevare: la cache e' un extra


# --- settore ------------------------------------------------------------------

def test_the_sector_is_asked_to_yahoo_only_once(monkeypatch):
    calls = []

    class _Ticker:
        def __init__(self, symbol):
            calls.append(symbol)

        @property
        def info(self):
            return {"sector": "Technology"}

    monkeypatch.setattr(sector.yf, "Ticker", _Ticker)

    assert sector.get_sector_etf("AAPL", TODAY) == "XLK"
    assert sector.get_sector_etf("AAPL", TODAY) == "XLK"
    assert sector.get_sector_etf("AAPL", TODAY + timedelta(days=1)) == "XLK"
    assert calls == ["AAPL"]


def test_a_network_failure_on_the_sector_is_not_cached(monkeypatch):
    """Mettere in cache un guasto di rete significherebbe decidere per 30
    giorni che questo titolo non ha settore."""
    def _boom(symbol):
        raise RuntimeError("rate limit")

    monkeypatch.setattr(sector.yf, "Ticker", _boom)
    assert sector.get_sector_etf("AAPL", TODAY) is None
    assert symbol_cache.get("AAPL", "sector_etf", TODAY, ttl_days=30) is symbol_cache.MISSING


# --- trimestrali --------------------------------------------------------------

def _ticker_returning(calendar, calls=None):
    class _Ticker:
        def __init__(self, symbol):
            if calls is not None:
                calls.append(symbol)
            self.calendar = calendar
    return _Ticker


def test_days_until_earnings_are_counted_from_the_market_date(monkeypatch):
    """Il conteggio parte dalla data di BORSA, non da quella del PC: di
    notte in Italia e' gia' il giorno dopo rispetto a New York, e la
    finestra di avviso si spostava di un giorno."""
    monkeypatch.setattr(risk_checks.yf, "Ticker", _ticker_returning({"Earnings Date": [date(2026, 9, 18)]}))

    check = risk_checks.earnings_check("AAPL", TODAY)

    assert check.days_until == 10


def test_a_timezone_aware_earnings_date_does_not_kill_the_whole_symbol(monkeypatch):
    """Prima l'aritmetica sulla data stava FUORI dal try: una data con fuso
    orario sollevava TypeError, che risaliva fino allo screener e faceva
    scartare l'intera analisi del titolo."""
    aware = pd.Timestamp("2026-09-18 12:00:00", tz="America/New_York")
    monkeypatch.setattr(risk_checks.yf, "Ticker", _ticker_returning({"Earnings Date": [aware]}))

    check = risk_checks.earnings_check("AAPL", TODAY)

    assert check.days_until == 10


def test_earnings_are_asked_once_and_the_days_are_recomputed_each_day(monkeypatch):
    calls = []
    monkeypatch.setattr(risk_checks.yf, "Ticker", _ticker_returning({"Earnings Date": [date(2026, 9, 18)]}, calls))

    assert risk_checks.earnings_check("AAPL", TODAY).days_until == 10
    # giorno dopo: nessuna nuova chiamata, ma un giorno in meno
    assert risk_checks.earnings_check("AAPL", TODAY + timedelta(days=1)).days_until == 9
    assert calls == ["AAPL"]


def test_a_past_earnings_date_is_asked_again(monkeypatch):
    """Data passata = trimestre nuovo da annunciare: la cache non deve
    tenersi una data vecchia."""
    calls = []
    monkeypatch.setattr(risk_checks.yf, "Ticker", _ticker_returning({"Earnings Date": [date(2026, 9, 9)]}, calls))

    risk_checks.earnings_check("AAPL", TODAY)
    risk_checks.earnings_check("AAPL", date(2026, 9, 10))   # la data salvata e' ormai passata

    assert calls == ["AAPL", "AAPL"]


def test_missing_earnings_data_stays_a_non_warning(monkeypatch):
    monkeypatch.setattr(risk_checks.yf, "Ticker", _ticker_returning({}))

    check = risk_checks.earnings_check("AAPL", TODAY)

    assert check.days_until is None and check.warn is False
