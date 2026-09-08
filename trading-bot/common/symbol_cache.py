"""Cache per i dati di ANAGRAFICA di un titolo: il settore GICS e la
prossima data di trimestrale.

Perche' esiste. La pipeline di screening chiama, per ogni titolo,
`yf.Ticker(symbol).info` (settore) e `yf.Ticker(symbol).calendar`
(trimestrali). Sono le due chiamate piu' lente di yfinance -- endpoint
diversi da quello delle barre, spesso 1-3 secondi ciascuna -- e sono anche
quelle che Yahoo limita piu' aggressivamente. Con l'universo full-market
significavano centinaia di chiamate ogni sera, ripetute da zero a ogni
ciclo, per due dati che non cambiano quasi mai:

  - il settore di un'azienda cambia forse una volta in anni;
  - la data della prossima trimestrale cambia una volta a trimestre.

Il costo non era solo il tempo. Quando Yahoo rispondeva con un rate-limit,
`get_sector_etf` restituiva None e il candidato perdeva la conferma
settoriale: il risultato dell'analisi dipendeva da quanto era di buon
umore Yahoo quella sera. Con la cache il dato resta stabile fra un ciclo e
l'altro, quindi le decisioni sono ripetibili.

Due livelli, e servono entrambi:
  - in memoria, caricato una volta sola per processo. Rileggere e
    riparsare il file JSON a ogni singola lettura avrebbe sostituito una
    chiamata di rete con migliaia di letture da disco di un file che con
    l'universo full-market arriva a migliaia di voci;
  - su disco, scritto una volta a fine scansione (`flush`), cosi' il
    lavoro fatto stasera serve anche domani sera.

Degrada senza mai sollevare (stesso principio di common/position_state.py):
una cache che non si puo' leggere o scrivere fa tornare il bot al
comportamento di prima -- piu' lento, non rotto."""
import atexit
import json
import logging
import os
import tempfile
from datetime import date

from common import config

log = logging.getLogger("bot")

CACHE_PATH = config.SYMBOL_CACHE_PATH

# Il settore di un'azienda e' di fatto statico: si ricontrolla ogni tanto
# solo per intercettare le riclassificazioni GICS, non perche' ci si aspetti
# che cambi.
SECTOR_TTL_DAYS = config.SYMBOL_CACHE_SECTOR_TTL_DAYS
# Le trimestrali si ricontrollano quando la data salvata e' passata (nuovo
# trimestre da annunciare) oppure quando il dato e' comunque vecchio: cosi'
# una data annunciata in ritardo viene recepita entro pochi giorni.
EARNINGS_TTL_DAYS = config.SYMBOL_CACHE_EARNINGS_TTL_DAYS

MISSING = object()

_data: dict | None = None
_dirty = False


def _read_file() -> dict:
    try:
        with open(CACHE_PATH) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        # A differenza dello stato posizioni, qui non si perde nulla di
        # irrecuperabile: la cache si puo' sempre ricostruire chiedendo di
        # nuovo a Yahoo. Si riparte da vuota, senza allarmi.
        log.warning("Cache anagrafica illeggibile (%s): %s. Riparto da vuota.", CACHE_PATH, exc)
        return {}


def _loaded() -> dict:
    global _data
    if _data is None:
        _data = _read_file()
    return _data


def _age_days(stamp, today: date) -> int | None:
    if not stamp:
        return None
    try:
        return (today - date.fromisoformat(str(stamp))).days
    except (ValueError, TypeError):
        return None


def get(symbol: str, field: str, today: date, ttl_days: int):
    """Valore in cache per (symbol, field) se non e' scaduto, altrimenti
    `MISSING`. `None` e' un valore valido e viene restituito: "Yahoo non
    conosce il settore di questo titolo" e' una risposta, e ripeterla ogni
    sera costa quanto la risposta utile."""
    entry = _loaded().get(symbol, {}).get(field)
    if not isinstance(entry, dict):
        return MISSING
    age = _age_days(entry.get("on"), today)
    # age < 0 = voce datata nel futuro (orologio spostato): si ributta via.
    if age is None or age < 0 or age > ttl_days:
        return MISSING
    return entry.get("value")


def put(symbol: str, field: str, value, today: date) -> None:
    global _dirty
    _loaded().setdefault(symbol, {})[field] = {"value": value, "on": today.isoformat()}
    _dirty = True


def flush() -> None:
    """Scrive su disco se c'e' qualcosa di nuovo. Scrittura atomica come per
    lo stato posizioni: file temporaneo nella stessa cartella + os.replace,
    cosi' chiudere la finestra del bot a meta' scrittura non lascia una
    cache troncata."""
    global _dirty
    if not _dirty or _data is None:
        return
    directory = os.path.dirname(CACHE_PATH)
    try:
        if directory:
            os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory or ".", prefix=".symbols-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(_data, f)
            os.replace(tmp, CACHE_PATH)
            _dirty = False
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError as exc:
        log.warning("Impossibile salvare la cache anagrafica (%s): %s", CACHE_PATH, exc)


def reset() -> None:
    """Svuota la copia in memoria (usata dai test; in esercizio non serve,
    il processo la carica una volta sola)."""
    global _data, _dirty
    _data = None
    _dirty = False


# Rete di sicurezza: se un ciclo termina per una strada che non passa dal
# flush esplicito, il lavoro di stasera non va comunque perso.
atexit.register(flush)
