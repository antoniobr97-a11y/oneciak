import logging
import logging.handlers
import os


def setup_logging() -> None:
    handlers = [logging.StreamHandler()]

    # Il file di log su disco e' un extra, non un requisito: se la cartella
    # "logs" (es. montata da host in Docker con un utente non-root) non e'
    # scrivibile, il bot deve continuare a girare loggando solo su stdout
    # (comunque visibile con `docker compose logs`) invece di crashare
    # all'avvio per un problema di permessi sui log.
    try:
        os.makedirs("logs", exist_ok=True)
        # A rotazione: il bot logga ogni giorno una scansione di centinaia
        # di titoli e resta acceso per mesi. Un file unico crescerebbe
        # senza limite finche' non riempie il disco.
        handlers.append(
            logging.handlers.RotatingFileHandler(
                "logs/bot.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
            )
        )
    except OSError as exc:
        print(f"Attenzione: impossibile scrivere logs/bot.log ({exc}), loggo solo su stdout.")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )

    # yfinance logga come ERROR i 404 su dati che per certi strumenti non
    # esistono proprio: il calendario delle trimestrali di un ETF, per
    # esempio ("No fundamentals data found for symbol: GDX"). Con l'universo
    # full-market ne arrivano a decine per ciclo, tutti innocui (il codice
    # chiamante li gestisce gia' come "nessun dato"), ma riempiono il log di
    # rosso e nascondono gli errori veri. Alzata la soglia: i problemi
    # rilevanti restano visibili perche' li segnala il nostro codice.
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
