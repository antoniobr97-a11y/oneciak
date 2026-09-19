"""Diario di bordo: cosa ha deciso il bot e con quali riserve.

Il broker registra le compravendite, non il perche'. Pattern e avvisi
esistono solo nel momento della decisione e dopo non si ricostruiscono.
Due cose devono valere sempre: (1) il diario non deve MAI far fallire un
ciclo, perche' interromperlo a meta' lascerebbe una posizione senza stop;
(2) l'abbinamento fra decisione ed esecuzione deve reggere il ritardo, che
puo' essere di giorni.
"""
from datetime import datetime, timedelta

import pytest

from common import diario


@pytest.fixture(autouse=True)
def diario_isolato(tmp_path, monkeypatch):
    monkeypatch.setattr(diario, "PERCORSO", str(tmp_path / "diario.jsonl"))


def test_scrive_e_rilegge():
    diario.annota(symbol="AAPL", pattern="TKO", avvisi=["settore non conferma"])

    (voce,) = diario.leggi()

    assert voce["symbol"] == "AAPL"
    assert voce["pattern"] == "TKO"
    assert voce["avvisi"] == ["settore non conferma"]
    assert "quando" in voce


def test_un_diario_che_non_si_puo_scrivere_non_ferma_il_bot(tmp_path, monkeypatch):
    """IL test. Un'eccezione qui interromperebbe il ciclo a meta',
    potenzialmente lasciando una posizione senza stop-loss: il diario e'
    una comodita', la protezione no.

    Il percorso e' impossibile sul serio: si chiede una cartella dove
    invece c'e' un file normale. Un percorso "che non esiste" non basta,
    perche' verrebbe semplicemente creato."""
    ostacolo = tmp_path / "sono-un-file"
    ostacolo.write_text("non sono una cartella")
    monkeypatch.setattr(diario, "PERCORSO", str(ostacolo / "diario.jsonl"))

    diario.annota(symbol="AAPL", pattern="TKO")   # non deve sollevare

    assert diario.leggi() == []


def test_una_riga_rotta_costa_una_voce_non_il_diario():
    diario.annota(symbol="AAPL", pattern="TKO")
    with open(diario.PERCORSO, "a", encoding="utf-8") as f:
        f.write("{questa non e' JSON\n")
    diario.annota(symbol="MSFT", pattern="Pivot")

    voci = diario.leggi()

    assert [v["symbol"] for v in voci] == ["AAPL", "MSFT"]


def test_senza_file_non_si_rompe():
    assert diario.leggi() == []


# --- abbinamento decisione -> operazione ----------------------------------

def _voce(symbol, pattern, quando):
    return {"symbol": symbol, "pattern": pattern, "quando": quando.isoformat(), "avvisi": []}


def test_abbina_la_decisione_all_operazione_anche_giorni_dopo():
    """Il bot piazza "compra sopra X": il prezzo puo' arrivarci giorni
    dopo. La decisione resta quella."""
    deciso = datetime(2026, 9, 1, 22, 16)
    voci = [_voce("HOOD", "Second Entry Pullback", deciso)]

    v = diario.voce_per("HOOD", deciso + timedelta(days=6), voci)

    assert v["pattern"] == "Second Entry Pullback"


def test_fra_due_decisioni_vince_la_piu_recente_prima_dell_apertura():
    """Il bot rinnova i pendenti con livelli nuovi: vale l'ultima."""
    voci = [
        _voce("KR", "vecchia", datetime(2026, 9, 1)),
        _voce("KR", "quella giusta", datetime(2026, 9, 10)),
    ]

    v = diario.voce_per("KR", datetime(2026, 9, 12), voci)

    assert v["pattern"] == "quella giusta"


def test_una_decisione_troppo_vecchia_non_si_abbina():
    """Oltre la finestra e' un'altra storia: i pendenti scadono."""
    voci = [_voce("VZ", "roba di mesi fa", datetime(2026, 1, 1))]

    assert diario.voce_per("VZ", datetime(2026, 9, 12), voci) is None


def test_una_decisione_successiva_non_puo_spiegare_un_operazione_precedente():
    voci = [_voce("T", "decisa dopo", datetime(2026, 9, 20))]

    assert diario.voce_per("T", datetime(2026, 9, 12), voci) is None
