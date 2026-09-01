FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Il bot legge le chiavi/parametri da .env (montato a runtime, vedi
# docker-compose.yml) -- non viene copiato nell'immagine.
CMD ["python", "bot.py", "schedule"]
