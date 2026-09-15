"""Minimo di azioni per aprire una posizione.

Nasce da una domanda dell'utente: "se metto 3-4.000 euro veri, il bot me
li brucia?". La risposta e' no -- rischia l'1% a operazione -- ma la
simulazione ha mostrato il problema opposto: con 1.500 EUR sul breve
termine la maggior parte dei candidati riceveva UNA azione.

Con una azione la scala di uscita del corso non esiste: non si puo'
vendere meta' di 1. Il bot terrebbe tutto fino alla SMA200, cioe' farebbe
una strategia diversa da quella misurata, senza dirlo a nessuno.
"""
import pytest

import bot
from common import config
from short_term.screener import Candidate
from tests.test_scan_symbol import _scan, _uptrend_with_pullback, no_network  # noqa: F401


def test_l_aritmetica_che_giustifica_il_minimo():
    """Il valore 4 non e' scelto a occhio: e' il primo per cui tutte e tre
    le uscite del corso hanno almeno un'azione."""
    for q in (1, 2, 3):
        meta, seconda, _ = bot._tranches(q)
        assert meta == 0 or seconda == 0, f"{q} azioni: la scala sarebbe completa, il minimo e' troppo alto"
    for q in (4, 5, 10):
        meta, seconda, runner = bot._tranches(q)
        assert meta > 0 and seconda > 0 and runner > 0, f"{q} azioni: scala incompleta"
    assert config.SHORT_TERM_MIN_SHARES == 4


def _candidato(qty: int) -> Candidate:
    from short_term import levels as levels_mod
    from short_term.patterns import PatternMatch
    from short_term.trend import TrendQualification
    return Candidate(
        symbol="TEST", direction="long", pattern="Pullback Semplice",
        trend=TrendQualification(direction="long", score=3, satisfied={}),
        levels=levels_mod.EntryLevels("long", 100.0, 95.0, 5.0),
        qty=qty, ribbon_aligned=True, sector_etf="XLK", sector_passes=True,
        earnings_warn=False, sr_too_close=False, price_blocks_trade=False,
        has_divergence=False,
    )


@pytest.mark.parametrize("qty", [0, 1, 2, 3])
def test_sotto_il_minimo_non_e_operabile(qty):
    assert _candidato(qty).is_actionable is False


@pytest.mark.parametrize("qty", [4, 5, 50])
def test_dal_minimo_in_su_e_operabile(qty):
    assert _candidato(qty).is_actionable is True


def test_con_il_minimo_a_zero_torna_il_comportamento_di_prima(monkeypatch):
    """L'interruttore deve poter tornare indietro: a 0 basta una azione."""
    monkeypatch.setattr(config, "SHORT_TERM_MIN_SHARES", 0)
    assert _candidato(1).is_actionable is True
    assert _candidato(0).is_actionable is False, "zero azioni non e' mai operabile"


def test_il_report_spiega_PERCHE_e_stato_saltato(monkeypatch, no_network):
    """Il candidato resta visibile con la sua nota: l'utente deve capire
    che e' una questione di capitale, non di grafico brutto."""
    monkeypatch.setattr(config, "SHORT_TERM_CAPITAL", 400.0)  # conto minuscolo
    candidati = _scan(_uptrend_with_pullback(), monkeypatch, capital=400.0)
    assert candidati, "il candidato e' sparito invece di essere spiegato"
    c = candidati[0]
    assert c.is_actionable is False
    assert any("scala di uscita" in n or "capitale insufficiente" in n for n in c.notes), c.notes
