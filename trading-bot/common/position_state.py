"""Piccolo stato persistente su file JSON per la gestione a scaglioni delle
posizioni di breve termine (STRATEGY.md 2.4 punto 2: 1R -> metà posizione;
3R -> altra quota; il resto lascia correre fino al segnale di inversione).

Il broker non conserva la size ORIGINALE di una posizione né a che
scaglione di uscita si è arrivati -- serve tracciarlo qui, tra un ciclo
schedulato e l'altro. Degrada senza crashare se il file non è scrivibile
(stesso principio di common/logger_setup.py): un problema di stato non
deve mai bloccare il ciclo di trading."""
import json
import logging
import os

from common import config

log = logging.getLogger("bot")

STATE_PATH = config.POSITION_STATE_PATH


def _load() -> dict:
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(state: dict) -> None:
    try:
        directory = os.path.dirname(STATE_PATH)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(STATE_PATH, "w") as f:
            json.dump(state, f)
    except OSError as exc:
        log.warning("Impossibile salvare lo stato posizioni (%s): %s", STATE_PATH, exc)


def get(symbol: str) -> dict:
    return _load().get(symbol, {})


def tracked_symbols() -> list[str]:
    return list(_load().keys())


def set_fields(symbol: str, **fields) -> None:
    state = _load()
    state.setdefault(symbol, {}).update(fields)
    _save(state)


def clear(symbol: str) -> None:
    state = _load()
    if symbol in state:
        del state[symbol]
        _save(state)
