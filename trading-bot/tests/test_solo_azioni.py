"""Solo azioni nel lato di breve termine (niente ETF).

Il 14 settembre 2026 il bot ha comprato IBIT -- un ETF che replica il
bitcoin -- come posizione piu' grande della serata. Non era un bug: il
suo universo includeva gli ETF perche' Alpaca li classifica come
"us_equity". Ma un ETF non ha settore, quindi saltava l'analisi
settoriale che il corso chiama "veramente fondamentale", ed entrava senza
quella conferma.

Il rischio nel correggere questo e' scartare troppo: un'AZIONE VERA a cui
manca il dato di settore (buco di Yahoo) non deve sparire. Per questo la
regola guarda il TIPO DI STRUMENTO, non la presenza del settore.
"""
from unittest.mock import patch

import pytest

from common import config, symbol_cache
from short_term import sector


@pytest.fixture(autouse=True)
def cache_pulita():
    symbol_cache.reset()
    yield
    symbol_cache.reset()


def _con_info(info: dict):
    """Sostituisce la risposta di Yahoo, che e' l'unica fonte di rete qui."""
    class _T:
        def __init__(self, *a, **k): pass
        @property
        def info(self): return info
    return patch.object(sector.yf, "Ticker", _T)


def test_una_azione_e_riconosciuta_come_azione():
    with _con_info({"sector": "Technology", "quoteType": "EQUITY"}):
        assert sector.is_equity("AAPL") is True


def test_un_etf_e_riconosciuto_come_non_azione():
    """IBIT: nessun settore, quoteType ETF."""
    with _con_info({"sector": None, "quoteType": "ETF"}):
        assert sector.is_equity("IBIT") is False


def test_una_azione_senza_settore_NON_viene_scambiata_per_un_etf():
    """Il test che protegge dall'errore opposto. Se la regola fosse 'non ha
    settore quindi e' un ETF', un titolo vero con un buco nei dati di Yahoo
    sparirebbe dall'universo senza che nessuno se ne accorga."""
    with _con_info({"sector": None, "quoteType": "EQUITY"}):
        assert sector.is_equity("TITOLO_SENZA_SETTORE") is True


def test_tipo_sconosciuto_non_scarta_niente():
    """Nel dubbio non si scarta: `None` significa 'non lo so', e scan_symbol
    scarta solo su un `False` esplicito."""
    with _con_info({"sector": "Technology"}):          # quoteType assente
        assert sector.is_equity("BOH") is None


def test_un_errore_di_rete_non_scarta_niente():
    class _Rotto:
        def __init__(self, *a, **k): pass
        @property
        def info(self): raise RuntimeError("Yahoo giu'")
    with patch.object(sector.yf, "Ticker", _Rotto):
        assert sector.is_equity("QUALSIASI") is None


def test_una_sola_chiamata_di_rete_per_settore_e_tipo():
    """Il tipo di strumento viaggia sulla stessa risposta gia' scaricata per
    il settore: se servisse una chiamata in piu', una scansione da 300
    titoli ne pagherebbe 300 in piu' ogni sera."""
    chiamate = []

    class _Contatore:
        def __init__(self, symbol, *a, **k): chiamate.append(symbol)
        @property
        def info(self): return {"sector": "Technology", "quoteType": "EQUITY"}

    with patch.object(sector.yf, "Ticker", _Contatore):
        sector.get_sector_etf("AAPL")
        sector.is_equity("AAPL")
    assert chiamate == ["AAPL"], f"chiamate di rete: {chiamate}"


def test_l_interruttore_esiste_ed_e_acceso():
    assert config.SHORT_TERM_STOCKS_ONLY is True
