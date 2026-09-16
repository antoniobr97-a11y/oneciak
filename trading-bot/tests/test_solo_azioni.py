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


# --- Regressione del 2026-09-16: l'ETF EWT e' passato col filtro acceso ---

def test_tipo_strumento_letto_anche_se_il_settore_e_gia_in_cache(tmp_path, monkeypatch):
    """Il bug che ha fatto comprare l'ETF EWT il 2026-09-16.

    Il titolo era gia' stato visto in un ciclo precedente, quindi il suo
    settore era in cache. `get_sector_etf` usciva subito restituendo il
    valore in cache e non scaricava niente -- percio' il tipo di strumento
    non veniva mai scritto, `is_equity` rispondeva "non so" (None) e
    l'ETF passava il filtro, che scarta solo su un False esplicito.
    """
    from datetime import date

    oggi = date(2026, 9, 16)
    # Cache vuota per davvero: reset() rilegge il file su disco, che nell'uso
    # reale e' pieno e falserebbe il test.
    monkeypatch.setattr(symbol_cache, "CACHE_PATH", str(tmp_path / "cache.json"))
    symbol_cache.reset()
    # Stato di partenza: il settore c'e' gia' (ciclo precedente), il tipo no.
    symbol_cache.put("EWT", "sector_etf", None, oggi)

    chiamate = []

    class FintoTicker:
        def __init__(self, simbolo):
            chiamate.append(simbolo)

        @property
        def info(self):
            return {"sector": None, "quoteType": "ETF"}

    monkeypatch.setattr(sector.yf, "Ticker", FintoTicker)

    assert sector.is_equity("EWT", today=oggi) is False
    assert chiamate == ["EWT"], "doveva scaricare il tipo di strumento, non fidarsi della cache del settore"


def test_un_fallimento_di_rete_non_diventa_un_verdetto(tmp_path, monkeypatch):
    """Se la rete cade si risponde "non so" (None), non "e' un'azione".

    Un fallimento non va messo in cache: sarebbe come decidere per 30
    giorni che questo strumento e' o non e' un'azione."""
    from datetime import date

    oggi = date(2026, 9, 16)
    class TickerCheEsplode:
        def __init__(self, simbolo):
            pass

        @property
        def info(self):
            raise RuntimeError("rete giu'")

    monkeypatch.setattr(sector.yf, "Ticker", TickerCheEsplode)

    assert sector.is_equity("QUALCOSA", today=oggi) is None
    assert symbol_cache.get("QUALCOSA", "quote_type", oggi, 30) is symbol_cache.MISSING
