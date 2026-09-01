# Trading Bot (Paper Trading)

Bot di trading azionario/ETF in **paper trading** (denaro simulato, zero
rischio) su Alpaca. Strategia: crossover di medie mobili (SMA) con filtro
RSI e stop-loss/take-profit basati su ATR.

> **Non è consulenza finanziaria.** Questo è un punto di partenza tecnico
> per sperimentare, non una strategia garantita. Testala a lungo in paper
> trading prima di anche solo pensare al denaro reale — e anche allora,
> fallo con capitale che puoi permetterti di perdere.

## Come funziona

- **Strategia** (`strategy.py`): se la SMA veloce (default 20 giorni)
  incrocia al rialzo la SMA lenta (default 50 giorni) e l'RSI(14) non è
  ipercomprato (<70), genera un segnale **BUY**. Se la SMA veloce incrocia
  al ribasso mentre si ha una posizione aperta, genera **SELL**.
- **Rischio** (`risk.py`): ogni operazione rischia solo l'1% dell'equity
  del conto (configurabile), con dimensione della posizione calcolata
  sulla distanza dallo stop-loss (basato su ATR), e un tetto massimo per
  posizione (default 20% dell'equity).
- **Esecuzione** (`broker.py`): ordini "bracket" su Alpaca — entrata a
  mercato + stop-loss + take-profit inviati insieme in un solo ordine.
- **Backtest** (`backtest.py`): simula la strategia su dati storici
  (yfinance, gratuito) per vedere come si sarebbe comportata in passato.
- **Bot live/paper** (`bot.py`): gira una volta al giorno (poco prima
  della chiusura di mercato) su ogni titolo della watchlist.

## Setup

1. **Crea un account Alpaca gratuito** su https://alpaca.markets e genera
   le chiavi **Paper Trading** dalla dashboard
   (https://app.alpaca.markets/paper/dashboard/overview →
   "Generate New Key" con il toggle "Paper Trading" attivo). Sono chiavi
   di simulazione: nessun denaro reale è coinvolto.

2. Installa le dipendenze (consigliato un virtualenv):
   ```bash
   cd trading-bot
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Copia `.env.example` in `.env` e inserisci le tue chiavi paper:
   ```bash
   cp .env.example .env
   # poi modifica .env con un editor
   ```
   Lascia `ALPACA_PAPER=true`. Personalizza `WATCHLIST` e i parametri di
   rischio/strategia se vuoi.

## Uso

**1. Backtest** (nessuna chiave richiesta, usa dati storici gratuiti):
```bash
python backtest.py                  # backtesta la watchlist di config.py, 2 anni
python backtest.py AAPL MSFT -p 5y  # simboli e periodo specifici
```
Mostra rendimento totale, numero di trade, win rate, drawdown massimo e
Sharpe ratio approssimato per ciascun simbolo. Ogni simbolo parte con
$10.000 indipendenti (non modella un portafoglio condiviso).

**2. Un singolo ciclo in paper trading** (richiede le chiavi Alpaca):
```bash
python bot.py --once
```
Controlla se il mercato è aperto, calcola il segnale per ogni titolo in
watchlist e — se applicabile — invia un ordine bracket paper.

**3. Bot schedulato** (gira ogni giorno feriale all'orario `RUN_TIME`):
```bash
python bot.py
```
Lascialo in esecuzione (es. in uno screen/tmux o come servizio) durante
l'orario di mercato USA (9:30–16:00 ET).

**4. Test unitari** (verificano la logica di segnale e sizing):
```bash
pip install pytest
pytest tests/
```

## Passare a denaro reale (quando/se sarai pronto)

1. Prima esegui il paper trading per settimane/mesi e valuta i risultati
   realmente, non solo il backtest.
2. Genera chiavi **live** dalla dashboard Alpaca (non paper).
3. Imposta `ALPACA_PAPER=false` in `.env`. Il bot loggherà un warning
   esplicito all'avvio quando questo è attivo.
4. Inizia con capitale minimo e `MAX_POSITION_PCT`/`RISK_PER_TRADE_PCT`
   bassi.

## Limiti noti / prossimi passi possibili

- Strategia intenzionalmente semplice: nessun filtro su regime di
  mercato, correlazione tra titoli, costi di transazione/slippage nel
  backtest, o gestione di eventi (earnings, notizie).
- Un layer opzionale con Claude potrebbe essere aggiunto per filtrare le
  entrate (es. evitare BUY se ci sono notizie negative imminenti), ma non
  è incluso in questa versione per mantenere il comportamento
  deterministico e testabile.
- Il backtest usa dati giornalieri di yfinance; il bot live usa i dati di
  Alpaca — piccole differenze tra le due fonti sono normali.
