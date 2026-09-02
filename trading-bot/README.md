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

python bot.py long-term-once
python bot.py long-term-once --execute
# Il ciclo AUTOMATICO di lungo termine (quello che lo scheduler lancia ogni
# giorno): Advanced = dentro/fuori per asset sulla SMA10 mensile, una
# decisione al mese; Harry Browne = ribilanciamento al 25% a ogni
# REBALANCE_FREQUENCY. Scegli quale con LONG_TERM_AUTO_STRATEGY in .env.
```

**Breve termine:**
```bash
python bot.py short-term-screen
# Scansiona SHORT_TERM_WATCHLIST, stampa i candidati (trend + pattern +
# settore + livelli + size), nessun ordine.

python bot.py short-term-once --execute
# Un ciclo completo: gestisce le posizioni aperte (chiusura a metà su 1R,
# stop al pareggio, seconda quota a 3R, runner, auto-riparazione dello
# stop se manca), poi screena ed entra sui nuovi candidati rispettando il
# tetto di rischio aggregato e la cassa disponibile (nessuna leva).

python bot.py schedule
# short-term-once + long-term-once, ogni giorno feriale a RUN_TIME
# (America/New_York). Il lungo termine e' idempotente: gira ogni giorno ma
# agisce una sola volta per mese (Advanced) o per trimestre (Harry Browne).
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
2. applica un **prefiltro di liquidità** (prezzo minimo
   `SHORT_TERM_MIN_PRICE_FULL_MARKET`, volume$ medio minimo
   `SHORT_TERM_MIN_DOLLAR_VOLUME`) usando gli snapshot di mercato Alpaca;
3. applica un **prefiltro di volatilità** (volatilità storica annualizzata
   minima `SHORT_TERM_MIN_ANNUALIZED_VOLATILITY_PCT`, default 25%) sui
   migliori sopravvissuti al passo precedente — aggiunto dopo che il primo
   backtest su un universo allargato (senza questo filtro) ha dato
   risultati peggiori della watchlist curata, vedi sotto;
4. tiene i migliori `SHORT_TERM_FULL_MARKET_MAX_SYMBOLS` (default 300) per
   volume$ tra chi supera entrambi i filtri — `short_term/screener.py:build_full_market_universe`;
5. passa questi titoli alla pipeline completa a 4 stadi (trend → pattern →
   settore → livelli), esattamente come farebbe con la watchlist fissa.

I prefiltri esistono perché far girare la pipeline completa ogni giorno su
migliaia di titoli sarebbe troppo lento e colpirebbe i rate-limit di
yfinance/Alpaca — è concettualmente lo stesso "Step 1: screening" del corso
(che nel corso usava Barchart/ProScreener, non replicabile). Nota: gli
snapshot Alpaca usano il feed IEX gratuito (una frazione del volume USA
reale), quindi volume$ e volatilità sono un ranking relativo utile a
scartare i titoli davvero illiquidi/piatti, non una misura esatta.
Con `SHORT_TERM_USE_FULL_MARKET=true` servono le chiavi Alpaca anche solo
per lo screening (senza, non serve — usa solo yfinance).

**Perché c'è anche il filtro di volatilità**: un primo test storico su un
universo allargato a 85 titoli (34 curati + 51 aggiunti, **senza** filtro
di volatilità) ha dato risultati peggiori della lista curata (CAGR
+1.53%/anno contro +2.69%, drawdown -33.6% contro -18.7% — vedi
STRATEGY.md "v4"). Causa probabile: titoli difensivi a bassa volatilità
(utility, consumer staples), su cui un sistema trend-following rende
storicamente peggio. Il filtro di volatilità qui sopra esiste apposta per
escluderli. **Nota però che il filtro non è stato validato in un nuovo
backtest storico dedicato** (richiederebbe rifare il test da capo con lo
stesso universo allargato ma con il filtro attivo) — è una correzione
motivata dal problema trovato, non una garanzia di risultato migliore.
Se vuoi il rischio più prevedibile possibile, la watchlist curata di
default resta la scelta più testata.

**Test:**
```bash
pip install pytest
pytest tests/
```
92 test unitari (money management, formule dei livelli, qualificatori di
trend, i 7 pattern, screener/universo full-market, broker (volatilità,
ordine delle operazioni sugli stop), ciclo automatico di lungo termine,
orchestrazione di `bot.py` con broker mockato). La
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
di breve termine E quello di lungo termine girano ogni giorno feriale
all'orario configurato in `RUN_TIME` (fuso orario di mercato USA, gestito
internamente).

**Comandi utili una volta avviato:**
```bash
docker compose logs -f          # segui i log in tempo reale
docker compose restart          # riavvia il bot (es. dopo aver cambiato .env)
docker compose down             # ferma tutto
git pull && docker compose up -d --build   # aggiorna il codice e riavvia
```

### Lungo termine automatico

Lo scheduler lancia anche `long-term-once --execute` ogni giorno, subito
dopo il ciclo di breve termine. Cosa fa dipende da `LONG_TERM_AUTO_STRATEGY`
in `.env`:

- **`advanced`** (default): per ognuno dei 5 ETF, guarda l'ultima chiusura
  **mensile chiusa** (mai il mese in corso) contro la SMA10 mensile: sopra →
  dentro (compra `LONG_TERM_CAPITAL × peso del profilo di rischio`, se non
  già in posizione), sotto → fuori (vende tutto, se in posizione). Una
  decisione al mese per asset, mai spostamenti di capitale tra asset
  (regole rigide di STRATEGY.md 1.2).
- **`harry_browne`**: riporta i 4 ETF al 25% di `LONG_TERM_CAPITAL` a ogni
  `REBALANCE_FREQUENCY` (trimestrale di default), mai a soglia di
  scostamento.
- **`none`**: lungo termine solo a mano (`long-term-status` / `long-term-pac`).

Il ciclo è **idempotente**: gira ogni giorno ma agisce una sola volta per
mese/trimestre (lo stato è in `state/positions.json`), quindi un giorno
festivo o un server spento nel giorno "giusto" non fa saltare il mese —
viene recuperato al primo giorno utile. Gli ETF di lungo termine vivono
nello stesso conto Alpaca delle azioni di breve termine ma sono tenuti
fuori dalla gestione a scaglioni, dal tetto di rischio e dall'equity usata
per il sizing del breve termine. Il PAC (versamenti periodici) resta
manuale, perché dipende da quando **tu** versi denaro sul conto.

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
  scaglioni (1R → chiusura a metà + stop a pareggio; 3R → altra quota +
  stop a pareggio riemesso sul residuo; 10-20% residuo lasciato correre
  fino all'inversione sulla SMA200) — validata nel backtest storico, vedi
  STRATEGY.md — più auto-riparazione dello stop (se una posizione non ha
  uno stop attivo al broker, viene riemesso) e tetto di cassa senza leva
- `bot.py:run_long_term_cycle`: ciclo automatico di lungo termine
  (Advanced mensile / Harry Browne trimestrale), idempotente per periodo
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
