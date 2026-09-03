"""Notifiche opzionali via webhook generico (Telegram, Discord, Slack o
qualunque endpoint che accetti un POST JSON) per eventi critici del bot
in esecuzione automatica: ordini eseguiti, errori. Senza rete "extra": usa
solo la libreria standard (urllib), nessuna nuova dipendenza.

Senza ALERT_WEBHOOK_URL configurato, alert() non fa nulla (no-op) --
il bot resta utilizzabile anche senza notifiche configurate."""
import json
import logging
import urllib.request

from common import config

log = logging.getLogger("bot")


def alert(message: str, level: str = "info") -> None:
    """Invia una notifica best-effort. Non solleva mai eccezioni: un
    problema con il servizio di notifica non deve mai far fallire il ciclo
    di trading che la sta generando."""
    if not config.ALERT_WEBHOOK_URL:
        return

    prefix = {"info": "ℹ️", "warning": "⚠️", "error": "🚨"}.get(level, "")
    text = f"{prefix} Trading bot: {message}".strip()

    # Formato compatibile sia con webhook generici ({"text": ...}, usato da
    # Slack/Discord-compatibili) sia con un endpoint personalizzato che
    # legge lo stesso campo "text".
    # Tutto dentro il try, compresa la costruzione della richiesta: un URL
    # malformato in .env fa sollevare ValueError gia' a Request(), cioe'
    # PRIMA di urlopen, e farebbe fallire il ciclo di trading che sta solo
    # cercando di mandare una notifica. except Exception e' deliberato: la
    # promessa di questa funzione e' "non solleva mai".
    try:
        payload = json.dumps({"text": text}).encode("utf-8")
        request = urllib.request.Request(
            config.ALERT_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(request, timeout=10)
    except Exception as exc:
        log.warning("Notifica webhook fallita (ignorata): %s", exc)
