FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non eseguire come root: se un domani girasse anche codice/dipendenze di
# terze parti compromesse, un utente non privilegiato limita il danno.
RUN useradd --create-home --shell /bin/false botuser \
    && mkdir -p /app/logs \
    && chown -R botuser:botuser /app
USER botuser

# Il bot legge le chiavi/parametri da .env (montato a runtime, vedi
# docker-compose.yml) -- non viene copiato nell'immagine.
CMD ["python", "bot.py", "schedule"]
