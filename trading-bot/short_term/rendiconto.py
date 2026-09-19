"""Ricostruzione delle operazioni CHIUSE dagli ordini eseguiti.

Perche' esiste. Lo stato locale (common/position_state.py) tiene solo le
posizioni aperte, e `clear()` cancella la voce appena una si chiude: del
passato, in casa, non resta niente. Finche' e' cosi' non si puo' rispondere
alla domanda piu' importante -- "come sta andando davvero?" -- e tutto
quello che si sa del bot viene da simulazioni sul 2005-2026, non da lui.

Il broker pero' conserva ogni eseguito. Da quella lista si ricostruiscono
le operazioni complete: si segue il saldo di azioni titolo per titolo, e
ogni volta che torna a zero un'operazione e' finita.

Una scelta dichiarata: le uscite a scaglioni del corso (meta' a 1R, 30% a
3R, il resto che corre) sono TRE eseguiti diversi sullo stesso ingresso.
Qui contano come UNA operazione, perche' quella era: una decisione, un
rischio, un risultato. Contarle come tre gonfierebbe il numero di
operazioni e falserebbe la percentuale di successo -- le due uscite in
utile sarebbero due "vittorie" separate a fronte di un solo ingresso.
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Operazione:
    symbol: str
    apertura: datetime
    chiusura: datetime
    qty: float
    prezzo_ingresso: float           # medio ponderato degli acquisti
    prezzo_uscita: float             # medio ponderato delle vendite
    pnl: float
    uscite: int = 1                  # quanti eseguiti di uscita (la scala del corso ne fa 3)
    stop_iniziale: float | None = None

    @property
    def vinta(self) -> bool:
        return self.pnl > 0

    @property
    def pnl_pct(self) -> float:
        speso = self.prezzo_ingresso * self.qty
        return (self.pnl / speso * 100) if speso else 0.0

    @property
    def giorni(self) -> int:
        return max(0, (self.chiusura.date() - self.apertura.date()).days)

    @property
    def erre(self) -> float | None:
        """Risultato in multipli del rischio iniziale.

        E' la misura che conta: +2R vuol dire "ha guadagnato due volte
        quello che aveva messo a rischio". None quando lo stop iniziale
        non si riesce a ricostruire: meglio non dirlo che inventarlo.
        """
        if self.stop_iniziale is None:
            return None
        rischio = abs(self.prezzo_ingresso - self.stop_iniziale)
        if rischio <= 0:
            return None
        return (self.prezzo_uscita - self.prezzo_ingresso) / rischio


def _stop_iniziale(fills: list[dict], dopo: datetime) -> float | None:
    """Il primo stop piazzato dopo l'ingresso: e' il rischio che il bot
    aveva accettato. Se lo stop non e' mai stato eseguito ne' registrato
    fra gli eseguiti, resta None."""
    candidati = [
        f["stop_price"] for f in fills
        if f.get("stop_price") and f["filled_at"] >= dopo
    ]
    return candidati[0] if candidati else None


def ricostruisci(fills: list[dict], escludi: set[str] | None = None) -> list[Operazione]:
    """Operazioni chiuse, dalla piu' vecchia alla piu' recente.

    `escludi` serve a tenere fuori gli ETF del lungo termine: li' i "buy"
    sono ribilanciamenti trimestrali, non operazioni con un ingresso e
    un'uscita, e mescolarli falserebbe ogni statistica.
    """
    escludi = escludi or set()
    per_titolo: dict[str, list[dict]] = {}
    for f in sorted(fills, key=lambda x: x["filled_at"]):
        if f["symbol"] in escludi:
            continue
        per_titolo.setdefault(f["symbol"], []).append(f)

    operazioni: list[Operazione] = []
    for symbol, lista in per_titolo.items():
        saldo = 0.0
        costo = 0.0          # totale speso per le azioni in pancia
        ricavo = 0.0         # totale incassato uscendo
        qty_entrata = 0.0
        apertura = None
        uscite = 0
        for f in lista:
            segno = 1.0 if f["side"] == "buy" else -1.0
            if saldo == 0 and segno > 0:
                costo = ricavo = qty_entrata = 0.0
                uscite = 0
                apertura = f["filled_at"]

            if segno > 0:
                costo += f["qty"] * f["price"]
                qty_entrata += f["qty"]
            else:
                if saldo <= 0:
                    continue  # vendita senza posizione aperta: non e' un'operazione nostra
                venduto = min(f["qty"], saldo)
                ricavo += venduto * f["price"]
                uscite += 1
            saldo += segno * f["qty"]

            if saldo <= 1e-9 and qty_entrata > 0 and apertura is not None:
                operazioni.append(Operazione(
                    symbol=symbol,
                    apertura=apertura,
                    chiusura=f["filled_at"],
                    qty=qty_entrata,
                    prezzo_ingresso=costo / qty_entrata,
                    prezzo_uscita=ricavo / qty_entrata,
                    pnl=ricavo - costo,
                    uscite=uscite,
                    stop_iniziale=_stop_iniziale(lista, apertura),
                ))
                saldo = 0.0
                apertura = None
                qty_entrata = 0.0

    return sorted(operazioni, key=lambda o: o.chiusura)


def statistiche(operazioni: list[Operazione]) -> dict:
    """I numeri che servono per capire se la strategia sta funzionando.

    `profit_factor` = quanto si incassa per ogni euro perso. Sotto 1 si
    perde; sopra 1,5 la strategia ha un margine reale. E' la misura che il
    corso (video 45) indica di guardare ogni 3-6 mesi, non a ogni
    operazione.
    """
    if not operazioni:
        return {"totale": 0}

    vinte = [o for o in operazioni if o.vinta]
    perse = [o for o in operazioni if not o.vinta]
    guadagni = sum(o.pnl for o in vinte)
    perdite = abs(sum(o.pnl for o in perse))
    erre = [o.erre for o in operazioni if o.erre is not None]

    return {
        "totale": len(operazioni),
        "vinte": len(vinte),
        "perse": len(perse),
        "percentuale_successo": len(vinte) / len(operazioni) * 100,
        "pnl_totale": sum(o.pnl for o in operazioni),
        "guadagno_medio": guadagni / len(vinte) if vinte else 0.0,
        "perdita_media": -perdite / len(perse) if perse else 0.0,
        "profit_factor": (guadagni / perdite) if perdite else (float("inf") if guadagni else 0.0),
        "giorni_medi": sum(o.giorni for o in operazioni) / len(operazioni),
        "erre_medio": (sum(erre) / len(erre)) if erre else None,
        "con_erre": len(erre),
    }
