import logging
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
        handlers.append(logging.FileHandler("logs/bot.log"))
    except OSError as exc:
        print(f"Attenzione: impossibile scrivere logs/bot.log ({exc}), loggo solo su stdout.")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )
