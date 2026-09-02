# Trading Bot (Paper Trading)

Bot di trading su azioni/ETF USA in **paper trading** (denaro simulato, zero
rischio) su Alpaca. Implementa due strategie indipendenti descritte in
dettaglio in **[STRATEGY.md](STRATEGY.md)** — leggilo prima di toccare il
codice, è la specifica che il codice implementa:

- **`long_term/`** — portafogli di ETF (Harry Browne statico + Advanced
  dinamico trend-following), orizzonte 10+ anni, revisione mensile o meno
- **`short_term/`** — swing trading su azioni USA, pipeline a 4 stadi
  (qualificazione trend → pattern → analisi settoriale → livelli/sizing),
  posizioni tenute da giorni a mesi

> **Non è consulenza finanziaria.** Il codice implementa regole imparate da
> un corso di trading, con alcune assunzioni esplicite dove il corso non
> dava un numero preciso (segnalate nei commenti e in STRATEGY.md). Testalo
> a lungo in paper trading prima di anche solo pensare al denaro reale — e
> anche allora, fallo con capitale che puoi permetterti di perdere.

## Struttura

```
common/       config, dati storici (yfinance), broker Alpaca, logging
long_term/    Harry Browne, Advanced (profilo di rischio + segnale mensile), PAC
short_term/   indicatori, qualificazione trend, 7 pattern, settori, livelli,
              filtri di rischio, money management, screener end-to-end
bot.py        CLI: report e (opzionale) esecuzione paper trading
tests/        pytest
```

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

3. Copia `.env.example` in `.env` e personalizzalo (chiavi Alpaca, capitale,
   watchlist, profilo di rischio, parametri della strategia):
   ```bash
   cp .env.example .env
   ```
   Lascia `ALPACA_PAPER=true`.

## Uso

I comandi di solo report (`long-term-status`, `short-term-screen` senza
`--execute`) non richiedono le chiavi Alpaca, usano solo dati yfinance.

**Lungo termine:**
```bash
python bot.py long-term-status
# Allocazione target Harry Browne + pesi Advanced per il profilo di
# rischio configurato + segnale mensile SMA10 corrente per ogni asset.

python bot.py long-term-pac --deposit 500 --strategy harry_browne
python bot.py long-term-pac --deposit 500 --strategy advanced --execute
# Ordini di acquisto per un versamento PAC (non vende mai). --execute li
# invia davvero in paper trading, altrimenti stampa solo il report.
```

**Breve termine:**
```bash
python bot.py short-term-screen
# Scansiona SHORT_TERM_WATCHLIST, stampa i candidati (trend + pattern +
# settore + livelli + size), nessun ordine.

python bot.py short-term-once --execute
# Un ciclo completo: gestisce le posizioni aperte (chiusura a metà su 1R,
# stop al pareggio), poi screena ed entra sui nuovi candidati rispettando
# il tetto di rischio aggregato.

python bot.py schedule
# Come sopra, schedulato ogni giorno feriale a RUN_TIME (America/New_York).
```

### Universo full-market (scansionare tutto il mercato USA)

Di default il breve termine scansiona `SHORT_TERM_WATCHLIST`, la lista fissa
di 42 titoli validata nel backtest storico (i 34 USA originali + 8 ADR di
grandi aziende non-USA: Toyota, ASML, TSMC, Novo Nordisk, TotalEnergies,
Rio Tinto, Sony, BHP — vedi STRATEGY.md "v4" per il dettaglio). Per non
limitarsi del tutto ai "soliti titoli famosi" e coprire tutto il mercato
USA, imposta in `.env`:

```bash
SHORT_TERM_USE_FULL_MARKET=true
```

Con questa opzione il bot, a ogni ciclo:
1. chiede ad Alpaca la lista di **tutti** i titoli azionari USA tradable
   (NYSE/NASDAQ/ARCA/AMEX/BATS, esclusi OTC e simboli non "semplici" come
   warrant/unit/azioni privilegiate) — `common/broker.py:list_tradable_symbols`;
2. applica un **prefiltro di liquidità** veloce (prezzo minimo
   `SHORT_TERM_MIN_PRICE_FULL_MARKET`, volume$ medio minimo
   `SHORT_TERM_MIN_DOLLAR_VOLUME`) usando gli snapshot di mercato Alpaca,
   e tiene solo i migliori `SHORT_TERM_FULL_MARKET_MAX_SYMBOLS` (default
   300) per volume$ — `short_term/screener.py:build_full_market_universe`;
3. passa questi titoli alla pipeline completa a 4 stadi (trend → pattern →
   settore → livelli), esattamente come farebbe con la watchlist fissa.

Il prefiltro esiste perché far girare la pipeline completa ogni giorno su
migliaia di titoli sarebbe troppo lento e colpirebbe i rate-limit di
yfinance/Alpaca — è concettualmente lo stesso "Step 1: screening" del corso
(che nel corso usava Barchart/ProScreener, non replicabile). Nota: gli
snapshot di liquidità usano il feed IEX gratuito di Alpaca (una frazione del
volume USA reale), quindi il volume$ è un ranking relativo utile a scartare
i titoli davvero illiquidi, non una misura esatta del volume di mercato.
Con `SHORT_TERM_USE_FULL_MARKET=true` servono le chiavi Alpaca anche solo
per lo screening (senza, non serve — usa solo yfinance).

**Attenzione, risultato reale del backtest**: un test su un universo
allargato a 85 titoli (34 curati + 51 aggiunti) ha dato risultati
**peggiori**, non migliori, della lista curata (CAGR +1.53%/anno contro
+2.69%, drawdown -33.6% contro -18.7% — vedi STRATEGY.md "v4"). La causa
probabile è l'inclusione di titoli difensivi a bassa volatilità (utility,
consumer staples), su cui un sistema trend-following rende storicamente
peggio. La modalità full-market applica solo un prefiltro di liquidità
(prezzo, volume$), non uno di volatilità — quindi **non è il default
consigliato per chi vuole il rischio più basso possibile**: usala solo se
preferisci un universo più ampio pur sapendo che il backtest disponibile
mostra un rischio/rendimento peggiore della watchlist curata.

**Test:**
```bash
pip install pytest
pytest tests/
```
60 test unitari (money management, formule dei livelli, qualificatori di
trend, i 7 pattern, screener/universo full-market, orchestrazione di
`bot.py` con broker mockato). La
pipeline completa è stata anche sottoposta a uno stress-test con centinaia
di scenari sintetici multi-regime (vedi STRATEGY.md, "Calibrazione delle
soglie non specificate dal corso") per cercare bug non coperti dai singoli
test unitari.

## Deploy automatico (server sempre acceso)

Per far girare il bot ogni giorno senza intervento manuale serve un
computer sempre acceso. Un piccolo server cloud (VPS) da pochi euro/mese
va benissimo: il bot è leggero, non serve niente di potente.

**Provider adatti** (scegline uno, sono equivalenti per questo scopo):
Hetzner Cloud (CX22, ~4€/mese), DigitalOcean (Basic Droplet, ~6$/mese),
o qualunque altro VPS con Ubuntu 22.04/24.04.

### 1. Crea il server
Dal pannello del provider, crea una VM con Ubuntu 22.04 o 24.04 (l'opzione
più economica va bene). Annota l'indirizzo IP che ti assegna.

### 2. Collegati e installa Docker
```bash
ssh root@INDIRIZZO_IP
curl -fsSL https://get.docker.com | sh
```

### 3. Porta il codice sul server
```bash
git clone -b claude/ai-trading-bot-1rs29b https://github.com/antoniobr97-a11y/oneciak.git
cd oneciak/trading-bot
cp .env.example .env
nano .env   # incolla qui le tue chiavi Alpaca (vedi sezione Setup sopra)
```

### 4. Avvia il bot (resta acceso da solo)
```bash
docker compose up -d --build
```
Fatto: il container riparte da solo anche se il server si riavvia
(`restart: unless-stopped`), e lancia `python bot.py schedule` — il ciclo
di breve termine gira ogni giorno feriale all'orario configurato in
`RUN_TIME` (fuso orario di mercato USA, gestito internamente).

**Comandi utili una volta avviato:**
```bash
docker compose logs -f          # segui i log in tempo reale
docker compose restart          # riavvia il bot (es. dopo aver cambiato .env)
docker compose down             # ferma tutto
git pull && docker compose up -d --build   # aggiorna il codice e riavvia
```

**Nota:** questo automatizza solo il ciclo di **breve termine** (screening
+ gestione posizioni ogni giorno). Il lungo termine (Harry Browne/Advanced,
PAC) per sua natura si rivede al massimo una volta al mese/trimestre — ha
più senso lanciarlo a mano (`python bot.py long-term-status` /
`long-term-pac`) quando serve, che schedularlo.

### Notifiche (sapere cosa fa il bot senza controllare i log a mano)

Imposta `ALERT_WEBHOOK_URL` in `.env` per ricevere un messaggio quando il
bot apre una posizione, sposta uno stop a pareggio, o incontra un errore.
Funziona con qualunque servizio che accetti un POST JSON `{"text": "..."}`:

- **Telegram**: crea un bot con [@BotFather](https://t.me/BotFather), poi usa
  un servizio ponte tipo [ntfy.sh](https://ntfy.sh) o un piccolo webhook
  proxy verso `https://api.telegram.org/bot<TOKEN>/sendMessage` (serve un
  parametro `chat_id` in più, quindi Telegram richiede un proxy leggero,
  non accetta l'URL diretto)
- **Discord**: crea un webhook in Impostazioni canale → Integrazioni →
  Webhook, incolla l'URL direttamente in `ALERT_WEBHOOK_URL`
- **Slack**: crea un "Incoming Webhook" dall'app directory, stesso incolla-e-vai

Senza questa variabile configurata il bot funziona esattamente come prima
(nessuna notifica, solo log).

### Isolamento errori

Ogni titolo (gestione posizione aperta, invio nuovo ordine) è isolato in
un `try/except`: se una singola operazione fallisce (blip di rete, ordine
rifiutato dal broker), viene loggata e notificata, ma non blocca il resto
del ciclo — gli altri titoli vengono comunque processati lo stesso giorno.
Un guasto sistemico (es. Alpaca irraggiungibile) non uccide lo scheduler:
viene loggato/notificato e il ciclo successivo (il giorno dopo) riparte
normalmente.

## Cosa implementa (in breve)

Vedi STRATEGY.md per i dettagli e le soglie esatte. Riassunto:

- `long_term/harry_browne.py`: 4 ETF al 25%, sizing e ordini di
  ribilanciamento a date fisse
- `long_term/advanced_portfolio.py`: segnale mensile SMA(10) per asset,
  allocazione per profilo di rischio (`long_term/risk_profile.py`)
- `long_term/pac.py`: piano di accumulo che non vende mai, con tracciamento
  del prezzo medio di carico
- `short_term/trend.py`: i 6 qualificatori di trend (performance, gap,
  barre ad ampio range, armonia massimi/minimi, ADX, persistenza)
- `short_term/patterns.py`: i 7 pattern (Pullback Semplice, TKO, Pullback
  Persistente, Trend Pivot Pullback, Second Entry Pullback, Sacro Graal,
  Bowai)
- `short_term/sector.py`: forza relativa titolo/settore/mercato (ETF SPDR
  come proxy dei sotto-indici del corso, non liberamente disponibili)
- `short_term/levels.py`: formula di entrata/stop-loss basata sulla
  volatilità
- `common/position_state.py` + `bot.py`: gestione della posizione a
  scaglioni (1R → chiusura a metà + stop a pareggio; 3R → altra quota;
  10-20% residuo lasciato correre fino all'inversione sulla SMA200) —
  validata nel backtest storico, vedi STRATEGY.md
- `short_term/risk_checks.py`: supporti/resistenze, trimestrali, livello di
  prezzo, divergenze MACD settimanali
- `short_term/money_management.py`: sizing, tetto di rischio aggregato,
  matematica del drawdown, Profit Factor
- `short_term/screener.py`: mette insieme tutto quanto sopra su una
  watchlist, per entrambe le direzioni (long/short)

## Limiti noti

- I due indicatori proprietari del corso (Domanda/Offerta, PD90 Sentiment)
  e lo screener preconfigurato (Barchart/ProScreener) non sono replicabili
  senza le loro formule esatte — vedi la sezione finale di STRATEGY.md per
  le sostituzioni scelte.
- Diverse soglie numeriche non erano specificate esattamente nel corso
  (es. soglia % dei gap, soglia di prezzo "troppo costoso" per i long): sono
  calibrate su convenzioni standard di analisi tecnica (vedi STRATEGY.md),
  segnalate come assunzioni esplicite nel codice (`common/config.py`,
  `short_term/trend.py`, `short_term/risk_checks.py`) e configurabili via
  `.env`.
- **Nessun track record di trading reale.** Il backtest storico su dati
  2000-2026 (vedi STRATEGY.md, "Risultati del backtest storico") mostra un
  Profit Factor sopra 1 e drawdown contenuto con la disciplina completa
  attiva, ma resta sotto un semplice buy-and-hold sull'indice nello stesso
  periodo, su un universo di 20 titoli e con diverse semplificazioni
  dichiarate — nessun backtest sostituisce settimane/mesi di paper trading
  reale prima di fidarsi.
