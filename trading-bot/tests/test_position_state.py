"""Lo stato posizioni e' l'unico posto dove vivono size originale, stop e
stadio di uscita: il broker non li conserva. Perderlo significa che il bot
smette di gestire a scaglioni le posizioni aperte."""
import json
import os

from common import position_state


def _use_tmp(monkeypatch, tmp_path):
    path = tmp_path / "state" / "positions.json"
    monkeypatch.setattr(position_state, "STATE_PATH", str(path))
    return path


def test_state_survives_a_round_trip(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    position_state.set_fields("AAPL", stage="entered", original_qty=10)
    assert position_state.get("AAPL") == {"stage": "entered", "original_qty": 10}


def test_the_real_file_is_never_left_half_written(monkeypatch, tmp_path):
    """Su Windows il bot si ferma chiudendo la finestra, che uccide il
    processo: se succede durante un salvataggio non atomico il file resta
    troncato e lo stato di TUTTE le posizioni aperte e' perso."""
    path = _use_tmp(monkeypatch, tmp_path)
    position_state.set_fields("AAPL", stage="entered", original_qty=10)
    good = path.read_text()

    real_replace = os.replace

    def die_before_replace(src, dst):
        raise KeyboardInterrupt("finestra chiusa a meta' salvataggio")

    monkeypatch.setattr(os, "replace", die_before_replace)
    try:
        position_state.set_fields("AAPL", stage="1R_done")
    except KeyboardInterrupt:
        pass
    monkeypatch.setattr(os, "replace", real_replace)

    assert path.read_text() == good  # il file buono e' intatto
    assert json.loads(path.read_text())["AAPL"]["stage"] == "entered"
    # e nessun file temporaneo orfano lasciato in giro
    assert [f for f in os.listdir(path.parent) if f.endswith(".tmp")] == []


def test_a_corrupt_state_file_is_reported_and_kept(monkeypatch, tmp_path):
    """Tornare a stato vuoto in silenzio nasconderebbe la perdita: il ciclo
    dopo il bot direbbe solo 'gestione saltata' per ogni posizione."""
    path = _use_tmp(monkeypatch, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"AAPL": {"stage": "ent')  # troncato

    assert position_state.get("AAPL") == {}
    assert (path.parent / "positions.json.corrotto").exists()
