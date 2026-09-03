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
import tempfile

from common import config

log = logging.getLogger("bot")

STATE_PATH = config.POSITION_STATE_PATH


def _load() -> dict:
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        # Non si torna a "{}" in silenzio: uno stato illeggibile significa
        # che il bot ha perso size originale, stop e stadio di OGNI
        # posizione aperta, e dal ciclo dopo le gestirebbe "a mano" senza
        # che nessuno se ne accorga. Il file rotto viene conservato per
        # poterlo recuperare.
        broken = f"{STATE_PATH}.corrotto"
        try:
            os.replace(STATE_PATH, broken)
        except OSError:
            broken = "(non salvato)"
        log.error(
            "Stato posizioni illeggibile (%s): %s. File conservato in %s. "
            "Le posizioni aperte vanno ricontrollate a mano.", STATE_PATH, exc, broken,
        )
        return {}


def _save(state: dict) -> None:
    """Scrittura atomica: file temporaneo nella stessa cartella, poi
    os.replace (atomico su Windows e Linux).

    Scrivendo direttamente sul file vero, un'interruzione a meta' scrittura
    lo lascia troncato e quindi illeggibile. Non e' teorico: il modo in cui
    si ferma il bot su Windows e' chiudere la finestra, che uccide il
    processo -- se capita durante un salvataggio si perde lo stato di tutte
    le posizioni aperte."""
    directory = os.path.dirname(STATE_PATH)
    try:
        if directory:
            os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory or ".", prefix=".positions-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, STATE_PATH)
        except BaseException:
            # Anche su Ctrl+C / chiusura finestra: niente file temporanei
            # orfani, e soprattutto il file buono resta intatto.
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
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
