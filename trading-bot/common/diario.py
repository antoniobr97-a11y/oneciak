"""Diario di bordo: cosa ha deciso il bot, e con quali riserve.

Il rendiconto (short_term/rendiconto.py) ricostruisce dagli eseguiti del
broker quanto si e' guadagnato o perso. Ma il broker registra solo
compravendite: non sa con quale pattern il bot fosse entrato, ne' che
quella sera l'analisi settoriale non confermava, o che c'era una
resistenza a un decimo di R dall'ingresso.

Sono proprio quelle le informazioni che servono per imparare qualcosa.
"Le operazioni aperte nonostante tre avvisi rendono meno delle altre?" e'
una domanda a cui si puo' rispondere solo se gli avvisi sono scritti da
qualche parte nel momento in cui si decide. Dopo non si ricostruiscono
piu': dipendono dai dati di quel giorno.

File ad aggiunta in coda (una riga JSON per voce), mai riscritto: una
riga malformata costa una voce, non il diario intero.

Degrada senza mai sollevare, come common/position_state.py: se il disco e'
pieno o la cartella non e' scrivibile, il bot continua a operare e perde
solo la memoria di quella sera. Un diario non deve mai impedire
un'operazione, ne' peggio ancora interrompere un ciclo a meta' lasciando
una posizione senza stop.
"""
import json
import logging
import os
from datetime import date, datetime

from common import config

log = logging.getLogger("bot")

PERCORSO = os.path.join(os.path.dirname(config.POSITION_STATE_PATH), "diario.jsonl")


def annota(**campi) -> None:
    """Aggiunge una voce. Non solleva mai."""
    try:
        campi.setdefault("quando", datetime.now().isoformat(timespec="seconds"))
        os.makedirs(os.path.dirname(PERCORSO), exist_ok=True)
        with open(PERCORSO, "a", encoding="utf-8") as f:
            f.write(json.dumps(campi, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:
        log.warning("Diario non scritto (%s): %s. Il bot continua.", PERCORSO, exc)


def leggi() -> list[dict]:
    """Tutte le voci, dalla piu' vecchia. Le righe illeggibili si saltano."""
    voci = []
    try:
        with open(PERCORSO, encoding="utf-8") as f:
            for n, riga in enumerate(f, 1):
                riga = riga.strip()
                if not riga:
                    continue
                try:
                    voci.append(json.loads(riga))
                except json.JSONDecodeError:
                    log.warning("Diario: riga %d illeggibile, la salto.", n)
    except FileNotFoundError:
        return []
    except OSError as exc:
        log.warning("Diario illeggibile (%s): %s.", PERCORSO, exc)
        return []
    return voci


def _quando(voce: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(str(voce.get("quando")))
    except (TypeError, ValueError):
        return None


def voce_per(symbol: str, aperta_il: datetime, voci: list[dict], giorni_indietro: int = 40) -> dict | None:
    """La decisione che ha originato un'operazione aperta il `aperta_il`.

    Fra la decisione e l'esecuzione passa del tempo: il bot piazza un
    ordine "compra sopra X" e il prezzo puo' arrivarci giorni dopo, o mai.
    Quindi si cerca la voce piu' RECENTE su quel titolo che precede
    l'apertura, entro una finestra: oltre, e' un'altra storia (il bot
    rinnova i pendenti e li scarta dopo due settimane di setup non piu'
    valido).
    """
    if isinstance(aperta_il, date) and not isinstance(aperta_il, datetime):
        aperta_il = datetime.combine(aperta_il, datetime.min.time())
    riferimento = aperta_il.replace(tzinfo=None)

    candidate = []
    for v in voci:
        if v.get("symbol") != symbol:
            continue
        q = _quando(v)
        if q is None:
            continue
        distanza = (riferimento - q.replace(tzinfo=None)).days
        if 0 <= distanza <= giorni_indietro:
            candidate.append((q, v))
    if not candidate:
        return None
    return max(candidate, key=lambda x: x[0])[1]
