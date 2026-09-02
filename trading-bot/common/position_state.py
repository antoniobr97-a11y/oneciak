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


# Chiave riservata per lo stato NON legato a un singolo titolo (es. ultimo
# mese processato dal ciclo Advanced, data dell'ultimo ribilanciamento
# Harry Browne). Esclusa da tracked_symbols(), altrimenti la pulizia degli
# "orfani" in bot.py la cancellerebbe come un titolo non piu' in posizione.
_META_KEY = "_meta"


def get(symbol: str) -> dict:
    return _load().get(symbol, {})


def tracked_symbols() -> list[str]:
    return [k for k in _load().keys() if k != _META_KEY]


def get_meta(key: str, default=None):
    return _load().get(_META_KEY, {}).get(key, default)


def set_meta(key: str, value) -> None:
    state = _load()
    state.setdefault(_META_KEY, {})[key] = value
    _save(state)


def set_fields(symbol: str, **fields) -> None:
    state = _load()
    state.setdefault(symbol, {}).update(fields)
    _save(state)


def clear(symbol: str) -> None:
    state = _load()
    if symbol in state:
        del state[symbol]
        _save(state)
