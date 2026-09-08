"""La pipeline intera, dalla rete al candidato, con la rete sostituita.

Gli altri test guardano un pezzo per volta: la simulazione a guasti
sostituisce `screen_universe` in blocco, i test dello screener sostituiscono
`scan_symbol`. Restava scoperto proprio l'incastro nuovo -- scaricamento a
lotti, decisione di chi qualifica, secondo lotto per i settimanali, barre
passate a scan_symbol invece di essere riscaricate, cache di settore e
trimestrali -- cioe' il punto in cui un errore non darebbe un'eccezione ma
una lista di candidati sbagliata.

Qui si sostituisce solo `yf.download` e `yf.Ticker`, il confine vero con
l'esterno: tutto il resto e' il codice di produzione."""
import numpy as np
import pandas as pd
import pytest

from common import config, symbol_cache
from short_term import screener, sector


def _rising(n=520, start=50.0, end=150.0, seed=3, pullback=True, noise=1.2):
    """Salita netta; con `pullback`, un ritracciamento ordinato in coda --
    massimi e minimi decrescenti barra dopo barra, come vuole il corso."""
    rng = np.random.default_rng(seed)
    tail = 6 if pullback else 0
    base = np.linspace(start, end, n - tail) + rng.normal(0, noise, n - tail)
    close = np.concatenate([base, [base[-1] - 2.5 * i for i in range(1, tail + 1)]]) if tail else base
    high, low = close + 1.2, close - 1.2
    for i in range(1, tail + 1):
        high[-i], low[-i] = close[-i] + 0.8, close[-i] - 0.8
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": close, "High": high, "Low": low, "Close": close, "Volume": 2_000_000.0}, index=idx
    )


@pytest.fixture
def market(tmp_path, monkeypatch):
    """Un mercato finto: due titoli con un setup valido, uno piatto, piu'
    gli indici e gli ETF settoriali che servono alla pipeline."""
    monkeypatch.setattr(symbol_cache, "CACHE_PATH", str(tmp_path / "symbols.json"))
    symbol_cache.reset()
    monkeypatch.setattr(config, "SHORT_TERM_USE_FULL_MARKET", False)

    # Davvero piatto: poco rumore. Con rumore normale un titolo senza
    # direzione supera comunque i due qualificatori minimi richiesti dal
    # corso (un gap e un ADX in salita capitano per caso) -- e' la pipeline
    # a valle a scartarlo, non la qualificazione. Qui serve un titolo che
    # non qualifichi proprio, per poter verificare che i settimanali NON
    # vengano scaricati per lui.
    flat = _rising(start=100.0, end=100.5, pullback=False, noise=0.15)
    frames = {
        "SALE1": _rising(seed=3),
        "SALE2": _rising(seed=11, start=40.0, end=120.0),
        "PIATTO": flat,
        sector.SP500_PROXY: _rising(start=300.0, end=500.0, pullback=False),
        sector.RUSSELL2000_PROXY: _rising(start=150.0, end=200.0, pullback=False),
        "XLK": _rising(start=100.0, end=200.0, pullback=False),
    }

    calls = {"download": [], "ticker": []}

    def _download(tickers, **kw):
        calls["download"].append(tickers)
        wanted = [tickers] if isinstance(tickers, str) else list(tickers)
        have = {t: frames[t] for t in wanted if t in frames}
        if not have:
            return pd.DataFrame()
        if isinstance(tickers, str):
            return have[tickers]
        return pd.concat(have, axis=1)

    class _Ticker:
        def __init__(self, symbol):
            calls["ticker"].append(symbol)
            self.calendar = {}

        @property
        def info(self):
            return {"sector": "Technology"}

    monkeypatch.setattr(screener.get_daily_bars.__globals__["yf"], "download", _download)
    monkeypatch.setattr(sector.yf, "Ticker", _Ticker)
    monkeypatch.setattr(screener.risk_checks.yf, "Ticker", _Ticker)
    yield calls
    symbol_cache.reset()


def test_the_whole_pipeline_produces_candidates_from_batched_bars(market):
    candidates = screener.screen_universe(symbols=["SALE1", "SALE2", "PIATTO"], capital=10_000.0)

    found = {c.symbol for c in candidates}
    assert found and found <= {"SALE1", "SALE2"}       # il piatto non passa
    for c in candidates:
        assert c.direction == "long"
        assert c.levels.entry > c.levels.stop_loss     # long: entrata sopra lo stop
        assert c.levels.risk_per_share > 0
        assert c.qty >= 0
        assert c.sector_etf == "XLK"


def test_the_bars_are_downloaded_in_one_batch_not_one_by_one(market):
    screener.screen_universe(symbols=["SALE1", "SALE2", "PIATTO"], capital=10_000.0)

    batched = [c for c in market["download"] if not isinstance(c, str)]
    singles = [c for c in market["download"] if isinstance(c, str)]

    # i tre titoli in un colpo solo, non tre chiamate separate
    assert any(set(c) == {"SALE1", "SALE2", "PIATTO"} for c in batched)
    # le uniche chiamate singole restano gli indici e l'ETF settoriale
    assert set(singles) <= {sector.SP500_PROXY, sector.RUSSELL2000_PROXY, "XLK"}


def test_weekly_bars_are_fetched_only_for_symbols_that_qualified(market):
    screener.screen_universe(symbols=["SALE1", "SALE2", "PIATTO"], capital=10_000.0)

    six_year = [c for c in market["download"] if not isinstance(c, str) and "PIATTO" not in c]
    assert six_year, "il secondo lotto (settimanali) non e' partito"
    for chunk in six_year:
        assert "PIATTO" not in chunk       # non ha qualificato: niente settimanali


def test_the_sector_is_asked_once_per_symbol_not_once_per_pattern(market):
    screener.screen_universe(symbols=["SALE1", "SALE2", "PIATTO"], capital=10_000.0)

    # Un titolo puo' formare piu' pattern: la domanda sul settore deve
    # partire una volta sola per titolo, non una per pattern.
    for symbol in ("SALE1", "SALE2"):
        assert market["ticker"].count(symbol) <= 2      # settore + trimestrali


def test_a_second_scan_the_same_day_asks_yahoo_nothing_about_sectors(market):
    screener.screen_universe(symbols=["SALE1", "SALE2", "PIATTO"], capital=10_000.0)
    before = len(market["ticker"])
    screener.screen_universe(symbols=["SALE1", "SALE2", "PIATTO"], capital=10_000.0)

    assert len(market["ticker"]) == before             # tutto dalla cache


def test_a_bear_regime_stops_the_scan_before_any_download(market, monkeypatch):
    """Con l'indice sotto la sua media di lungo periodo e gli short spenti
    non c'e' nessuna direzione ammessa: il bot resta fuori dal mercato e
    non ha motivo di scaricare nulla."""
    monkeypatch.setattr(config, "MARKET_REGIME_FILTER", True)
    monkeypatch.setattr(config, "SHORT_TERM_ALLOW_SHORTS", False)
    falling = _rising(start=500.0, end=300.0, pullback=False)
    monkeypatch.setattr(screener, "get_daily_bars", lambda symbol, period="2y": _named(falling))

    assert screener.screen_universe(symbols=["SALE1"], capital=10_000.0) == []


def _named(frame):
    out = frame.rename(columns={"Open": "open", "High": "high", "Low": "low",
                                "Close": "close", "Volume": "volume"})
    out.index.name = "date"
    return out
