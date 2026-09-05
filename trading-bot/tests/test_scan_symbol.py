"""Test end-to-end di short_term/screener.py:scan_symbol.

Era la parte piu' grossa di codice mai eseguita da un test (coperta al
68%, con l'intero corpo di scan_symbol e _build_candidate mai toccato):
e' la funzione che trasforma le barre di un titolo in un Candidato con
entrata, stop e size, cioe' l'ultimo passaggio prima che parta un ordine
vero. Qui si usa una serie sintetica costruita per qualificare il trend e
formare un ritracciamento pulito; le chiamate di rete (settore,
trimestrali) sono sostituite."""
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from common import config
from short_term import risk_checks, screener, sector


def _uptrend_with_pullback():
    """Salita lenta, poi una gamba ripida (+50% in ~60 barre, cosi' il
    qualificatore di performance passa), poi 3 barre di ritracciamento a
    massimi e minimi decrescenti."""
    slow = list(np.linspace(50, 100, 240) + 1.5 * np.sin(np.linspace(0, 24 * np.pi, 240)))
    fast = list(np.linspace(100, 150, 57) + 1.5 * np.sin(np.linspace(0, 8 * np.pi, 57)))
    peak = fast[-1]
    c = np.array(slow + fast + [peak - 2.5, peak - 4.5, peak - 6.0])
    return pd.DataFrame(
        {"open": c, "high": c + 1.0, "low": c - 1.0, "close": c, "volume": [2e6] * len(c)},
        index=pd.date_range("2023-06-01", periods=len(c), freq="B"),
    )


def _flat(n=300, value=100.0):
    c = np.full(n, value)
    return pd.DataFrame(
        {"open": c, "high": c + 1, "low": c - 1, "close": c, "volume": [1e6] * n},
        index=pd.date_range("2023-06-01", periods=n, freq="B"),
    )


@pytest.fixture
def no_network(monkeypatch):
    monkeypatch.setattr(sector, "get_sector_etf", lambda symbol: "XLK")
    monkeypatch.setattr(screener.sector, "get_sector_etf", lambda symbol: "XLK")
    monkeypatch.setattr(risk_checks, "earnings_check", lambda symbol: risk_checks.EarningsCheck(None, None))
    monkeypatch.setattr(screener.risk_checks, "earnings_check", lambda symbol: risk_checks.EarningsCheck(None, None))


def _scan(daily, monkeypatch, capital=10_000.0):
    weekly = daily.resample("W-FRI").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    monkeypatch.setattr(screener, "get_daily_bars", lambda s, period="1y": daily)
    monkeypatch.setattr(screener, "get_weekly_bars", lambda s, period="6y": weekly)
    monkeypatch.setattr(screener, "_sector_bars", lambda etf: _flat())
    index = _flat()
    return screener.scan_symbol("TEST", capital, index, index, directions=("long",))


def test_a_qualifying_uptrend_becomes_a_candidate(monkeypatch, no_network):
    candidates = _scan(_uptrend_with_pullback(), monkeypatch)

    assert candidates, "una salita netta con ritracciamento pulito deve produrre un candidato"
    c = candidates[0]
    assert c.symbol == "TEST" and c.direction == "long"
    assert c.trend.qualifies
    assert c.levels.entry > c.last_close        # buy stop SOPRA il prezzo, come da corso
    assert c.levels.stop_loss < c.levels.entry
    assert c.levels.risk_per_share == pytest.approx(c.levels.entry - c.levels.stop_loss)
    assert c.qty > 0 and c.is_actionable


def test_the_size_risks_exactly_one_percent_of_capital(monkeypatch, no_network):
    """floor(capitale x 1% / rischio per azione): la regola di money
    management del corso, verificata sui numeri veri del candidato."""
    monkeypatch.setattr(config, "SHORT_TERM_RISK_PER_TRADE_PCT", 1.0)
    c = _scan(_uptrend_with_pullback(), monkeypatch, capital=10_000.0)[0]

    assert c.qty == int(10_000.0 * 0.01 // c.levels.risk_per_share)
    assert c.qty * c.levels.risk_per_share <= 100.0   # mai piu' dell'1%


def test_double_the_capital_doubles_the_size(monkeypatch, no_network):
    small = _scan(_uptrend_with_pullback(), monkeypatch, capital=10_000.0)[0]
    big = _scan(_uptrend_with_pullback(), monkeypatch, capital=20_000.0)[0]
    assert big.qty == 2 * small.qty
    assert big.levels.entry == small.levels.entry     # i livelli non dipendono dal capitale


def test_a_flat_series_produces_nothing(monkeypatch, no_network):
    assert _scan(_flat(), monkeypatch) == []


def test_too_little_history_is_skipped(monkeypatch, no_network):
    short = _uptrend_with_pullback().iloc[-100:]      # sotto MIN_HISTORY_BARS
    assert _scan(short, monkeypatch) == []


def test_an_unknown_sector_is_noted_but_does_not_block(monkeypatch, no_network):
    monkeypatch.setattr(screener.sector, "get_sector_etf", lambda symbol: None)
    candidates = _scan(_uptrend_with_pullback(), monkeypatch)
    assert candidates
    assert candidates[0].sector_passes is False
    assert any("settore non determinato" in n for n in candidates[0].notes)


def test_only_the_requested_directions_are_scanned(monkeypatch, no_network):
    """Col filtro di regime attivo il ciclo passa una sola direzione: lo
    screener non deve produrre candidati nell'altra."""
    candidates = _scan(_uptrend_with_pullback(), monkeypatch)
    assert candidates and all(c.direction == "long" for c in candidates)


def test_the_warnings_the_user_reads_are_attached_to_the_candidate(monkeypatch, no_network):
    """Le righe con "!" nel log escono da qui: sono note sul candidato, non
    divieti. Il bot le stampa e manda comunque l'ordine (scelta misurata,
    vedi STRATEGY.md v12)."""
    c = _scan(_uptrend_with_pullback(), monkeypatch)[0]
    assert isinstance(c.notes, list)
    # settore piatto contro titolo in salita: l'analisi settoriale non conferma
    assert c.sector_passes is False
    assert any("settoriale" in n for n in c.notes)
    assert c.is_actionable is True   # nota, non divieto
