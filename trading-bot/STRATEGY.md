# Strategia di trading — documento di riferimento

Questo documento è la specifica completa implementata dal codice in questa
cartella. È una sintesi originale, scritta da zero, del metodo di
investimento che l'utente ha studiato in un corso di formazione a
pagamento — non è una trascrizione del corso, ma la traduzione delle sue
regole operative in un linguaggio preciso e implementabile.

Due strategie indipendenti, entrambe **trend-following** (si segue il
mercato, non lo si prevede; l'unica variabile davvero controllabile è il
rischio):

- **Lungo termine**: portafogli di ETF, orizzonte 10+ anni, rivisti al
  massimo una volta al mese
- **Breve termine**: azioni USA, posizioni tenute da giorni a mesi, riviste
  quotidianamente sul timeframe giornaliero

---

## Parte 1 — Lungo termine (ETF)

### 1.1 Portafoglio statico "Harry Browne" (Permanent Portfolio)

Allocazione fissa, 4 ETF al 25% ciascuno, scelti per correlazione inversa
tra loro (in qualunque regime di mercato, almeno uno dei quattro rende):

| Asset | Peso | Note |
|---|---|---|
| Azionario | 25% | ETF globale/ampio (es. tipo MSCI World), preferibilmente hedged EUR |
| Obbligazionario lungo termine | 25% | Duration 7-10+ anni |
| Obbligazionario breve termine | 25% | Duration 1-3 anni |
| Oro | 25% | Un solo ETF sull'oro, preferibilmente hedged EUR |

**Selezione di ciascun ETF** (in ordine di importanza):
1. Diversificazione (ETF ampio, non concentrato su un singolo paese/settore)
2. Capitalizzazione del fondo (AUM) — più alta, più liquido
3. Volume di scambi (media mobile ~20 periodi sul volume giornaliero)
4. Controvalore medio giornaliero (volume medio × prezzo) > ~€200.000

**Sizing:** `quote = floor(capitale × 25% / prezzo_ETF)`

**Ribilanciamento** (capitale investito in un'unica soluzione): a **date
fisse** (trimestrale/semestrale/annuale — mai a soglia di scostamento,
capitali grandi ribilanciano più spesso). Si vende ciò che è sopra al 25%
target e si ricompra ciò che è sotto, per riportare l'allocazione a
25/25/25/25.

**Piano di Accumulo (PAC):** versione "non si vende mai" — a ogni
versamento si compra solo ciò che serve a riportare ogni asset verso il
25%, senza mai vendere; ribilanciamento implicito attraverso gli acquisti.
Se l'importo periodico è troppo piccolo, allungare l'intervallo tra i
versamenti (es. semestrale invece che mensile) piuttosto che fare tanti
micro-trade.

### 1.2 Portafoglio dinamico "Advanced" (trend-following mensile)

5 asset class (aggiunge l'immobiliare/REIT a Harry Browne): azionario,
obbligazionario lungo, obbligazionario breve, oro, immobiliare. ETF
**diversi** da quelli usati per Harry Browne (mai sovrapporli).

**Segnale (timeframe MENSILE, SMA a 10 periodi):**
- BUY: il prezzo era sotto la SMA, la incrocia dal basso E la chiusura
  mensile risulta sopra la SMA
- SELL: il prezzo era sopra la SMA, la incrocia dall'alto E la chiusura
  mensile risulta sotto la SMA
- Revisione una volta al mese; se non c'è un incrocio pulito, si mantiene
  la posizione corrente (dentro se già dentro, fuori se già fuori)

**Allocazione per asset class, in base al profilo di rischio** (da
questionario a punteggio):

| Punteggio | Profilo | Obbligazioni | Azionario | Oro | Immobiliare |
|---|---|---|---|---|---|
| <18 | molto basso | 100% | 0% | 0% | 0% |
| 19–22 | basso | 85–90% | 5–7.5% | 5–7.5% | 0% |
| 23–28 | medio | 65–70% | 15–20% | 5–10% | 0–5% |
| 29–32 | alto | 50–55% | 30–35% | 5–10% | 5–10% |
| 33+ | molto alto | 25–40% | 40–55% | 10% | 10% |

**Regole rigide:** mai spostare capitale su un ETF diverso solo perché
segnala BUY prima degli altri; mai superare il tetto percentuale del
proprio profilo per asset class; il profilo di rischio si rivede solo dopo
anni, non ogni pochi mesi. Leva finanziaria opzionale, mai oltre 2x (al
limite 3x) — non è parte del protocollo base.

### 1.3 Rischi da gestire (validi per entrambi i portafogli di lungo termine)

- **Rischio prezzo**: mitigato solo dall'avere sempre un motivo di uscita
  definito in anticipo (qui: il segnale mensile della SMA)
- **Rischio emittente** (soprattutto obbligazioni): diversificare su molti
  emittenti (da qui l'uso di ETF obbligazionari, già diversificati)
- **Rischio liquidità**: soglie minime di controvalore/volume (sopra)
- **Rischio cambio**: preferire strumenti in EUR o hedged, dato l'orizzonte
  pluriennale

---

## Parte 2 — Breve termine (azioni USA, swing trading)

Pipeline di analisi a 4 stadi, applicata su timeframe **giornaliero** (con
il **settimanale** usato come timeframe di conferma/setup):

```
Step 1: Screening → Qualificazione trend → Pattern
Step 2: Analisi settoriale (forza relativa titolo/settore/mercato)
Step 3: Conferma con fascio di medie mobili multiple
Step 4: Indicatori di conferma → calcolo livelli → position sizing
```

### 2.1 Qualificazione del trend (6 parametri)

Finestra tipica: ultimi 2-3 mesi. Il titolo deve avere una direzione chiara
(mai laterale). Bastano **2-3 dei 6** qualificatori soddisfatti (raro
trovarli tutti):

1. **Performance** ≥ +30% (long) o ≤ -30% (short) dal minimo al massimo del periodo
2. **Gap** nella direzione del trend (almeno uno)
3. **Barre ad ampio range** con chiusura nel 25% estremo del proprio range
   (superiore per i long, inferiore per gli short), meglio se concentrate
   nella parte più recente
4. **Massimi/minimi "armonici"**: sequenza coerente di massimi e minimi
   crescenti (long) o decrescenti (short)
5. **ADX(14)** > 30, oppure in salita anche sotto 30 (misura la forza del
   trend, non la direzione)
6. **Persistenza**: una retta di tendenza attraverso le barre del periodo
   ne intercetta la maggior parte delle ultime ~20

### 2.2 I 7 pattern (1 di inversione + 6 di continuazione)

Un pattern non è un segnale di acquisto — è un "vale la pena continuare
l'analisi". L'ordine scatta solo dopo aver calcolato i livelli esatti
(2.4). Tutti i pattern di continuazione condividono il concetto di **barra
di setup**: la barra del ritracciamento con l'estremo più profondo
raggiunto finora (minimo più basso per i long, massimo più alto per gli
short); si aggiorna barra dopo barra finché il pattern non scade o non
scatta l'ingresso.

| # | Pattern | Condizione distintiva | Durata pullback |
|---|---|---|---|
| 1 | Pullback Semplice | Massimi/minimi decrescenti (long) dopo un nuovo massimo di 2-3 mesi | 2–7 barre |
| 2 | TKO (Trend Knockout) | Barra di sell-off ad ampio range che rompe ≥2-3 minimi precedenti | come sopra, può evolvere in pullback |
| 3 | Pullback Persistente | Come #1, ma nasce da una fase di persistenza (≥20 barre) invece che da un trend generico | 2–7 barre |
| 4 | Trend Pivot Pullback | Pattern a 3 barre: la centrale fa un massimo più alto di entrambe le vicine, poi fallisce | 2–5 barre |
| 5 | Second Entry Pullback | Una barra supera il massimo precedente intraday ma chiude sotto (breakout fallito) — quella diventa la nuova barra di setup | 2–5 barre |
| 6 | Sacro Graal (Holy Grail) | Il pullback tocca la EMA(20) invece di un numero fisso di barre; richiede ADX>30 e crescente | fino al tocco della EMA20 |
| 7 | Bowai (UNICO pattern di inversione) | 3 medie (SMA10, EMA20, EMA30) invertono l'ordine in ≤5 giorni, dopo un minimo/massimo di almeno 6 mesi | 1 barra |

Regole di conteggio comuni: le barre **inside** (range contenuto in quello
della barra precedente) non contano ai fini del conteggio delle barre di
pullback; le barre **outside** contano normalmente.

Ingresso ed uscita, per tutti i pattern di continuazione: sopra/sotto il
massimo/minimo della barra di setup (livello esatto in 2.4). Per il Bowai
vale lo stesso principio ma sulla singola barra di setup dell'inversione.

**Nucleo minimo dichiarato:** Pullback Semplice + TKO coprono da soli circa
il 90% delle operazioni di continuazione. Gli altri 4 pattern di
continuazione sono varianti per situazioni meno nitide, non strettamente
necessarie a un primo sistema funzionante.

### 2.3 Analisi settoriale (Step 2)

Non è un requisito assoluto (tranne per il Bowai, dove è quasi
obbligatorio), ma riduce il rischio di operare contro il gruppo a cui il
titolo appartiene.

- Il settore deve muoversi nella stessa direzione del titolo
- Forza relativa titolo-vs-settore: crescente per i long, decrescente per gli short
- Forza relativa settore-vs-mercato (S&P 500 **e** Russell 2000, per un
  controllo incrociato large-cap/small-cap): stesso criterio
- Historical Volatility ideale: titolo > settore > mercato (altrimenti
  tanto vale comprare un ETF sull'indice)
- Bonus (non richiesto): lo stesso pattern presente anche sul settore

### 2.4 Calcolo dei livelli (entrata, stop-loss, target)

Usa l'**Indicatore di Volatilità**: l'escursione media giornaliera in
valore assoluto (es. media mobile del range max-min sulle ultime N barre,
tipicamente 10).

```
LONG:
  entrata   = chiusura(barra_di_setup) + volatilità
              (se cade dentro il range della barra, spostare appena sopra il massimo)
  stop_loss = minimo(barra_di_setup) − volatilità

SHORT (speculare):
  entrata   = chiusura(barra_di_setup) − volatilità
  stop_loss = massimo(barra_di_setup) + volatilità
```

`rischio_per_azione = |entrata − stop_loss|`

**Gestione della posizione dopo l'ingresso** (identica per tutti i pattern):
1. Al raggiungimento di **1R** (rischio/beneficio 1:1: `entrata ± rischio_per_azione`)
   → vendere metà posizione, spostare lo stop-loss al pareggio (prezzo di
   entrata) sulla metà restante — da quel momento zero rischio
2. Valutare la chiusura (totale o parziale) intorno a 3R/4R, o lasciar
   correre oltre con chiusure progressive; una piccola quota (10-20%) può
   restare indefinitamente come posizione "di lungo respiro"
3. Uscita anticipata comunque su segnali di inversione (Bowai opposto,
   chiusura sotto medie mobili di lungo periodo tipo 100/200)
4. Lo stop-loss non si allarga mai dopo l'apertura, solo si stringe

### 2.5 Filtri di rischio aggiuntivi (prima di aprire la posizione)

- **Supporti/resistenze** sul timeframe settimanale: per i long controllare
  le resistenze sopra il prezzo, per gli short i supporti sotto. Validità
  del livello data da volume, ampiezza del movimento originato e recenza
  (~5-6 anni). Se il primo livello significativo dista meno di ~3× il
  rischio dall'entrata, il rischio della singola operazione aumenta
- **Trimestrali (earnings)**: controllare la data prossima; se entro
  10-15 giorni, valutare se evitare l'operazione
- **Prezzo del titolo**: evitare long su titoli molto costosi (poco spazio
  per un grande movimento %) e short su titoli molto economici (spazio di
  ribasso limitato, minimo teorico zero); short preferibilmente sopra
  $80-100
- **Divergenze** tra prezzo e istogramma MACD sul timeframe settimanale:
  aumentano il rischio se contrarie alla direzione del trade

### 2.6 Indicatori di conferma (Step 3-4)

Mai decisionali da soli — solo conferma. Se in disaccordo tra loro, il
rischio percepito aumenta.

- **MACD(12,26,9)** sul timeframe **settimanale**: solo la direzione
  dell'istogramma (ultimi 3-5 periodi) deve concordare col trade
- **ADX(14)** giornaliero: stesso criterio della qualificazione del trend
- **Fascio di EMA multiple** giornaliero: brevi (3,5,8,10,12,15) sopra le
  lunghe (30,35,40,45,50,60) per i long, sotto per gli short — se
  "intrecciate" il trend non è pulito, meglio scartare
- **Historical Volatility** (20 periodi): vedi 2.3

Indicatori proprietari del corso citati ma non replicabili (formula non
divulgata: Domanda/Offerta, PD90 Sentiment) — **non implementati** in
questo codice; il loro ruolo (conferma direzionale extra) è comunque
coperto dagli altri indicatori sopra.

### 2.7 Money management

- Rischio per operazione: **1-2% massimo** del capitale dedicato alla
  strategia (0.5-1% per chi inizia), **costante** tra un'operazione e l'altra
- `numero_azioni = floor((capitale × rischio%) / (rischio_per_azione / cambio_valuta))`
- Rischio aggregato massimo su tutte le posizioni aperte contemporaneamente
  = rischio% × numero posizioni aperte — restare indicativamente entro il
  **10-12%** dello scenario peggiore (tutte a stop-loss insieme)
- Drawdown: la matematica del recupero è fortemente asimmetrica (-20%
  richiede +25%; -50% richiede +100%; -70% richiede +233%) — da qui il
  tetto di rischio basso
- Profit Factor = Σ(guadagni) / Σ(|perdite|), da monitorare ogni 3-6 mesi,
  non per singolo trade

### 2.8 Disciplina operativa (regole comportamentali)

- Mai comprare "perché il prezzo è sceso ed è a sconto", mai shortare
  perché "è salito troppo" — solo la strategia decide, mai un'opinione
- Mai investire sul sentito dire (notizie, consigli) — il prezzo sconta
  già le notizie pubbliche
- Pianificare tutto (entrata, uscita, size, target) **prima** di aprire, e
  poi seguire solo il piano
- Analisi fatta a mercati chiusi, in buone condizioni fisiche/mentali
- Nessun attaccamento a un titolo specifico o a un'idea; se ci sono più
  dubbi che conferme, scartare l'operazione
- Diversificare per settore nel portafoglio, non concentrarsi tutto su un
  singolo settore
- Ridurre l'operatività quando il mercato generale è laterale (il sistema
  è trend-following, senza trend non ha vantaggio statistico)

---

## Calibrazione delle soglie non specificate dal corso

Il corso descrive alcuni criteri come giudizio visivo sul grafico invece
che con un numero esatto (gap "significativo", barra ad "ampio range",
fascio di EMA "pulito" vs "intrecciato", persistenza di una retta di
tendenza). Dove manca un numero preciso, il codice usa una convenzione
standard di analisi tecnica — cercata esplicitamente, non inventata a
caso — configurabile in `.env`:

| Soglia | Default | Convenzione usata |
|---|---|---|
| Gap significativo | ≥0.5× la volatilità media | soglia relativa alla volatilità del titolo, non una % fissa uguale per tutti (un 1% è enorme per un'utility, insignificante per un titolo che si muove il 5%/giorno) -- convenzione superiore documentata nella letteratura su gap/ATR-based thresholds |
| Barra ad ampio range | ≥1.5× la volatilità media | "wide-range bar" = range oltre un multiplo del range medio/ATR, non un percentile del periodo (dipenderebbe troppo dalla finestra scelta) |
| Swing high/low (armonia, S/R) | fractal a 2 barre per lato (giornaliero), 3 sul settimanale | convenzione di Williams (fractal standard a 5 barre); finestra più ampia sul settimanale per privilegiare solo i livelli più significativi |
| Fascio di EMA "pulito" | separazione minima 0.3% del prezzo tra brevi e lunghe | oltre al semplice ordinamento (che da solo si presta a falsi positivi quando le medie sono ordinate ma quasi a contatto) |
| Persistenza | adattamento a una retta (≥60% delle barre entro 1 ATR) **e** movimento netto minimo nella direzione testata | una retta piatta si adatta perfettamente anche a un mercato laterale: senza il secondo controllo il qualificatore risultava vero anche senza una vera direzione (bug trovato con stress-test sintetico, poi corretto) |

**Verifica**: oltre alla test suite (`tests/`), l'intera pipeline
(qualificazione trend, tutti e 7 i pattern, calcolo livelli, money
management, orchestrazione in `bot.py`) è stata sottoposta a uno
stress-test con centinaia di combinazioni di dati OHLCV sintetici
multi-regime (trend forte, laterale, alta volatilità, inversione a V,
mercato piatto, storico troppo corto) per cercare eccezioni non gestite e
comportamenti illogici. Ha trovato e fatto correggere 3 bug reali:
un qualificatore di persistenza cieco alla direzione (risultava vero anche
in controtendenza o su un mercato piatto), un controllo di armonia che
trattava un pareggio di prezzo come "discendente", e un crash su
DataFrame vuoti/troppo corti in `adx_qualifier` e nei pattern detector.

## Risultati del backtest storico (dati reali, non sintetici)

Oltre allo stress-test sintetico sopra (verifica che il *codice* sia
corretto), la strategia è stata simulata su **dati di mercato reali**
2000-2026 per stimare se abbia un vantaggio economico reale. Metodologia
completa e limiti dichiarati in fondo a questa sezione.

### Lungo termine (Harry Browne + Advanced)

| Strategia | Periodo | CAGR | Max drawdown | Sharpe |
|---|---|---|---|---|
| Harry Browne | 2008-2026 (18 anni) | +6.14%/anno | -19.9% | 0.80 |
| *Buy & hold SPY, confronto* | *stesso periodo* | *+12.32%/anno* | *-47.2%* | *0.69* |
| Advanced (profilo medio) | 2009-2026 (17 anni) | +3.30%/anno | -10.4% | 0.60 |
| *Buy & hold SPY, confronto* | *stesso periodo* | *+14.20%/anno* | *-33.7%* | *0.87* |

Entrambe rendono meno del semplice buy-and-hold in un periodo che è stato
uno dei più forti rialzi azionari della storia — ma è esattamente il
compromesso dichiarato di un Permanent Portfolio: non massimizzare il
rendimento, minimizzare i colpi grossi (drawdown un terzo di quello di
SPY per Harry Browne).

### Breve termine (swing trading azioni)

Simulazione giorno per giorno, senza look-ahead, 2000-2026. Tre versioni
successive, ciascuna un miglioramento validato sulla precedente:

| Metrica | v1: solo Step 1 | v2: + settore/filtri | **v3: + universo ampio + uscita a scaglioni** |
|---|---|---|---|
| Universo | 20 blue chip | 20 blue chip | **34 titoli (+ 14 growth/volatili: AMZN, NVDA, NFLX, GOOGL, TSLA, META...)** |
| Gestione uscita | 1R + SMA200 | 1R + SMA200 | **1R (50%) → 3R (30%) → runner 10-20% fino a SMA200** |
| CAGR | +0.92%/anno | +1.31%/anno | **+2.69%/anno** |
| Max drawdown | -38.6% | -16.0% | -18.7% |
| Sharpe | 0.14 | 0.23 | **0.39** |
| Profit Factor | 0.98 | 1.28 | **1.36** |
| Win rate per operazione | 47.6% | 51.7% | 52.0% |
| Operazioni (26.7 anni) | 1.138 | 271 | 446 |

**v2 → v3**: due cambi motivati, non tentativi a caso. (1) Un sistema
trend-following è documentato rendere meglio su titoli che si muovono
davvero (Turtle Traders operavano su future/commodity volatili, non blue
chip stabili) — ampliare l'universo con titoli growth/alta-volatilità ha
quasi raddoppiato il CAGR. (2) Il backtest v1/v2 semplificava la gestione
della posizione a un solo stadio (1R); implementare la regola COMPLETA del
corso (STRATEGY.md 2.4 punto 2: chiusura scaglionata a 1R/3R, piccola quota
lasciata correre) ha migliorato ulteriormente Sharpe e Profit Factor. Il
bot live implementa ora la stessa gestione a scaglioni v3 (vedi
`common/position_state.py`, `bot.py`).

Anche nella versione migliore, il CAGR resta ben sotto un semplice
buy-and-hold sull'indice nello stesso periodo — il long è profittevole, lo
short resta in perdita netta (probabile effetto del trend secolare
rialzista USA 2000-2026, in cui operare short va strutturalmente
controcorrente). Il 2025 e il 2026 (fine campione) mostrano performance
negative, da monitorare.

**Limiti dichiarati di questo backtest** (perché i numeri sopra vadano
letti come indicativi, non come garanzia):
- Nessun filtro trimestrali/earnings: non esiste un calendario storico
  gratuito affidabile per un backtest di questa ampiezza
- Conferma settoriale e filtri di rischio applicati come blocco rigido
  (scarta il trade), più severo del bot live che li tratta come nota
  informativa (tranne per il Bowai, dove restano quasi obbligatori)
- Mappatura settore→ETF statica sulla classificazione attuale, non le
  riclassificazioni GICS storiche nel tempo
- Slippage stimato (0.05% per fill), non commissioni/slippage reali di un
  broker specifico
- Universo comunque limitato a 34 titoli (v3) / 85-110 titoli (v4, vedi
  sotto). Il bot live supporta anche l'universo full-market
  (`SHORT_TERM_USE_FULL_MARKET=true` in `.env`, vedi README "Universo
  full-market") — scansiona tutti i titoli USA tradable su Alpaca con un
  prefiltro di liquidità, invece della watchlist fissa — ma **questa
  modalità non è stata backtestata alla sua scala reale (migliaia di
  titoli)**: il test più vicino disponibile è il v4 sotto (85 titoli, senza
  prefiltro di liquidità/volatilità aggiuntivo)

### v4: universo allargato a 85 titoli USA + 25 ADR non-USA (test separato)

Domanda dell'utente: "le azioni che il bot deve cercare non sono le solite
famose, deve cercare tutto il mercato statunitense" + volontà di
diversificare oltre i titoli USA. Due backtest aggiuntivi rispondono a
entrambe:

**Prima un bug trovato e corretto prima di fidarsi dei numeri**: il primo
giro includeva le 25 ADR insieme agli 85 titoli USA, ma restituiva **zero
operazioni su tutte le 25 ADR**. Causa: la conferma settoriale nel motore
di backtest è un filtro rigido (scarta il trade se non passa, per ogni
pattern — più severo del bot live, vedi sopra) e le ADR non avevano una
voce in `SECTOR_MAP` (mappatura statica del backtest) → `sector_etf=None`
→ scartate sempre, indipendentemente dal pattern. Non era un giudizio di
mercato, era un artefatto del filtro. Fix: aggiunta una mappatura
settoriale approssimata sul business reale di ciascuna ADR (es. Toyota →
consumo discrezionale, banche europee/canadesi → finanziario), poi
ripetuto il test. **Nota**: questo bug esisteva solo nel motore di
backtest, non nel bot live — `short_term/sector.py` legge il settore reale
da yfinance dinamicamente per qualunque titolo incluse le ADR, e lo tratta
comunque solo come nota informativa (tranne Bowai), mai come blocco.

| Metrica | v3 (34 titoli, sopra) | **v4a: +51 titoli USA (85 tot.)** | **v4b: solo 25 ADR non-USA** |
|---|---|---|---|
| CAGR | +2.69%/anno | **+1.53%/anno** | **+1.13%/anno** |
| Max drawdown | -18.7% | **-33.6%** | **-19.1%** |
| Sharpe | 0.39 | **0.20** | **0.23** |
| Profit Factor | 1.36 | **1.11** | **1.19** |
| Win rate per operazione | 52.0% | 49.6% | 54.9% |
| Operazioni (26.7 anni) | 446 | 839 posizioni | 304 posizioni |

**Risultato onesto, non quello sperato**: allargare l'universo da 34 a 85
titoli USA **peggiora** tutte le metriche corrette per il rischio, non le
migliora — CAGR quasi dimezzato, drawdown quasi raddoppiato. Causa più
probabile: i 51 titoli aggiunti includono parecchie difensive/utility a
bassa volatilità (DUK, SO, NEE, CL, KMB, GIS, MO, PM) — un sistema
trend-following rende storicamente peggio su titoli che si muovono poco
(stessa logica Turtle Traders già citata per v2→v3, qui in direzione
opposta). **Lezione concreta: più titoli non significa più soldi** — la
qualità/volatilità dell'universo conta più della quantità grezza.

Di conseguenza `build_full_market_universe` (`short_term/screener.py`) ora
applica anche un prefiltro di volatilità storica minima
(`SHORT_TERM_MIN_ANNUALIZED_VOLATILITY_PCT`, default 25% annualizzata,
`common/broker.py:volatility_snapshot`), oltre a quello di liquidità, per
escludere le difensive piatte prima della pipeline completa. **Attenzione**:
questo filtro non è stato ri-validato con un nuovo backtest storico dedicato
sullo stesso universo di 85 titoli (richiederebbe un altro giro di ore in
background) — è una correzione motivata direttamente dal problema
diagnosticato sopra, non un risultato nuovamente misurato. La watchlist
curata di 42 titoli resta l'unica configurazione con un backtest storico
completo alle spalle; la modalità full-market resta disponibile per chi
preferisce un universo più ampio, ma senza la stessa garanzia empirica.

Le 25 ADR da sole, invece, si comportano ragionevolmente bene — PF 1.19 e
Sharpe 0.23 sono vicini alla qualità del v3 curato, non diluiti come
l'espansione USA generica. Per titolo (posizioni distinte, min. 4 per
essere considerate):

| Titolo | Operazioni | Win rate | PnL totale |
|---|---|---|---|
| ASML (Paesi Bassi) | 22 | 54.5% | +$834 |
| TM — Toyota (Giappone) | 4 | 75.0% | +$702 |
| TSM — TSMC (Taiwan) | 16 | 56.2% | +$593 |
| NVO — Novo Nordisk (Danimarca) | 12 | 66.7% | +$544 |
| TTE — TotalEnergies (Francia) | 11 | 63.6% | +$488 |
| RIO — Rio Tinto (UK/Australia) | 20 | 70.0% | +$471 |
| SONY (Giappone) | 19 | 68.4% | +$352 |
| BHP (Australia) | 15 | 73.3% | +$319 |

Le altre 17 ADR testate (BP, SHEL, HSBC, SAP, UL, DEO, BUD, AZN, NVS, SNY,
ERIC, NOK, TD, RY, BABA, JD, PDD) erano deboli, in perdita, o con troppo
poche operazioni per fidarsene. Solo le 8 sopra sono state aggiunte a
`SHORT_TERM_WATCHLIST` di default (vedi `common/config.py`) — diversificazione
reale oltre i soliti nomi USA, ma solo dove il backtest la conferma, non
un'aggiunta a caso.

### v5: filtro di regime di mercato (SPY vs SMA200)

**Ipotesi, e da dove viene.** In *tutti* i backtest v1-v4 il lato long è
profittevole e il lato short è in perdita netta (Profit Factor ~0.7). La
letteratura dice la stessa cosa in modo indipendente: l'S&P 500 rende in
media circa +12%/anno quando è sopra la sua media a 200 giorni e circa
-4%/anno quando è sotto ([backtest della regola](https://www.quantifiedstrategies.com/200-day-moving-average/)),
e i portafogli long-only battono i long-short in quasi tutti i punti della
distribuzione ([Short selling and market anomalies](https://www.sciencedirect.com/science/article/abs/pii/S1386418118303525)).
Lo Step 2 del corso chiede già che titolo e settore siano allineati al
mercato; il filtro di regime applica lo stesso principio all'indice:
**long solo se SPY chiude sopra la SMA200, short solo se sotto.**

**Test a parità di tutto il resto** (stesso motore v3/v4, stesso universo
validato di 42 titoli = 34 USA + 8 ADR, 2000-2026):

| Metrica | 42 titoli, senza filtro | **42 titoli, con filtro (v5)** |
|---|---|---|
| CAGR | +3.85%/anno | **+4.08%/anno** |
| Max drawdown | -16.3% | **-15.7%** |
| Sharpe | 0.48 | **0.52** |
| Profit Factor per operazione | 1.41 | **1.54** |
| Win rate per operazione | 54.6% | 54.5% |
| Operazioni (26.7 anni) | 546 | 470 |
| Long: n / PF | 432 / 1.62 | 397 / 1.71 |
| Short: n / PF | 114 / 0.70 | 73 / 0.67 |

Due cose da leggere in questi numeri, onestamente:
- Il filtro **migliora ogni metrica**, ma di poco (Sharpe +0.04, PF +0.13,
  drawdown -0.6 punti). Non è una svolta: è un filtro che toglie
  operazioni controtendenza (76 in meno) e migliora la qualità media di
  quelle rimaste. Il beneficio maggiore è negli anni orso: 2008 -3.9%
  contro -7.8%, 2011 -3.0% contro -5.7%, 2022 -7.4% contro -9.5%.
- Nota a margine, ma importante: la colonna "senza filtro" su 42 titoli è
  già migliore del v3 su 34 (CAGR 3.85% contro 2.69%, Sharpe 0.48 contro
  0.39) — conferma indipendente che le 8 ADR aggiunte in v4 aiutano
  davvero, non solo da sole.
- Gli **short restano in perdita anche col filtro** (PF 0.67). Il filtro
  non li salva: li riduce. Questo è il motivo del test v6 sotto.

Il filtro è nel bot live (`MARKET_REGIME_FILTER=true` di default,
`short_term/screener.py:allowed_directions`), disattivabile da `.env`.

### v6: niente short (solo long, con filtro di regime)

**Ipotesi.** Il corso insegna entrambe le direzioni e il codice le
implementa per intero (pattern speculari, livelli, gestione). Ma il lato
short è in perdita netta in **ogni** backtest fatto — v1, v2, v3, v4a, v4b
(ADR), v5 — con Profit Factor tra 0.67 e 0.70, anche quando il filtro di
regime lo limita ai soli mercati ribassisti. Non è un caso di un singolo
universo o periodo: 2000-2026 include tre mercati orso (2000-02, 2008,
2022) e gli short perdono lo stesso. La spiegazione più semplice è
strutturale: nei ribassi le azioni scendono più in fretta ma con rimbalzi
violenti che colpiscono lo stop (asimmetria documentata, vedi fonti in
v5); il sistema, pensato per cavalcare trend, sul lato short paga stop
più spesso di quanto incassi.

**Test a parità di tutto il resto** (v5 + short disattivati):

| Metrica | v5: regime, long+short | **v6: regime, solo long** |
|---|---|---|
| CAGR | +4.08%/anno | **+4.53%/anno** |
| Max drawdown | -15.7% | **-13.0%** |
| Sharpe | 0.52 | **0.61** |
| Profit Factor per operazione | 1.54 | **1.71** |
| Win rate per operazione | 54.5% | 55.5% |
| Operazioni (26.7 anni) | 470 | 393 |
| Anni orso: 2002 / 2008 / 2022 | -4.9% / -3.9% / -7.4% | **-1.0% / -2.9% / -4.4%** |

È il miglioramento più netto tra tutte le versioni: ogni metrica migliora
e il drawdown scende di quasi 3 punti, esattamente nella direzione del
"rischio basso" scelto. Nel bot live gli short sono quindi **disattivati
di default** (`SHORT_TERM_ALLOW_SHORTS=false`): quando SPY è sotto la
SMA200 il bot semplicemente non apre nuove posizioni e gestisce solo
quelle esistenti. Chi vuole seguire il corso alla lettera li riattiva da
`.env`, sapendo cosa dicono i numeri.

Nota di metodo, per non ingannarsi: v5 e v6 sono state decise **prima** di
vedere i risultati, su un'ipotesi motivata (letteratura + risultati
coerenti di tutte le versioni precedenti), non cercando a tentativi la
configurazione che rendesse di più. Sono state testate due sole varianti,
entrambe con una ragione economica chiara — non cento parametri fino a
trovare quello "giusto" per il passato.

Durante la costruzione di questi backtest sono stati trovati e corretti
**5 bug** specifici della simulazione storica (non nel codice del bot): un
bias look-ahead nel segnale mensile (usava il mese in corso invece
dell'ultimo chiuso), una leva impossibile nel money management (nessun
tetto sul capitale davvero disponibile), un disallineamento di calendario
tra titoli che faceva sparire posizioni aperte dal calcolo dell'equity per
un giorno, un crash sui titoli con storico più corto (quotati dopo il
2000) quando la finestra di analisi cadeva prima della loro quotazione, e
la mappatura settoriale mancante per le ADR (v4, sopra) che le escludeva
sempre dal test.

## Audit del codice live (bug trovati e corretti prima del paper trading)

Dopo i backtest, revisione riga per riga del codice che manda ordini veri
(`bot.py`, `common/broker.py`), cercando errori che nessun backtest può
vedere perché riguardano il rapporto col broker, non la strategia. Trovati
e corretti **5 problemi reali**, tutti coperti da test:

1. **Stop-loss che scadeva a fine giornata (il più grave).** L'ordine di
   entrata era un OTO con time-in-force DAY: la gamba stop-loss eredita il
   TIF del padre, quindi lo stop veniva cancellato alla chiusura dello
   stesso giorno in cui il bot entra (alle 15:50). Dal giorno dopo ogni
   posizione restava **senza protezione**, per tutta la sua durata (giorni
   o settimane). Fix: GTC. In più, auto-riparazione: a ogni ciclo, se una
   posizione non ha uno stop attivo al broker, viene riemesso (allo stop
   originale prima di 1R, al pareggio dopo) e notificato — il livello di
   stop originale è ora salvato nello stato apposta per questo.
2. **Chiusura parziale rifiutata dal broker.** Su Alpaca un ordine di
   vendita aperto (lo stop) riserva le azioni: la vendita di metà
   posizione a 1R veniva inviata PRIMA di cancellare lo stop → rifiuto
   "insufficient qty available", ogni giorno, per sempre (l'errore era
   catturato e loggato, ma la regola 1R non veniva mai eseguita). Fix:
   cancella gli stop → chiusura parziale → nuovo stop sul residuo.
3. **Stop a pareggio con quantità sbagliata dopo 3R.** Dopo la seconda
   chiusura parziale lo stop non veniva riemesso: quello esistente copriva
   la quantità pre-3R (più azioni di quelle rimaste) e, se scattato,
   avrebbe tentato di vendere azioni non possedute. Fix: riemesso sul nuovo
   residuo. Stessa cura per la chiusura totale del runner (cancella gli
   stop prima di chiudere).
4. **Leva nascosta nel sizing live.** Il conto paper Alpaca ha margine di
   default: il sizing a rischio % non limitava l'esposizione in dollari
   alla cassa disponibile (identico al bug trovato e corretto nel
   backtest). Fix: quantità limitata a `floor(cassa / prezzo)`, cassa
   decrementata man mano nel ciclo — nessuna leva, come nel backtest.
   Inoltre gli ETF di lungo termine (stesso conto) sono ora esclusi dal
   conteggio del tetto di rischio, dalla gestione a scaglioni e
   dall'equity su cui si calcola il rischio % del breve termine.
5. **Segnale mensile Advanced calcolato sul mese in corso.** Il resample
   mensile include il mese parziale come ultima barra e il segnale la
   trattava come "chiusura mensile" — la stessa classe di bug look-ahead
   trovata nel backtest, presente anche nel codice live. Fix: solo mesi
   chiusi (`long_term/advanced_portfolio.py:closed_monthly_closes`).

Nella stessa revisione il lungo termine è stato **automatizzato**
(`bot.py:run_long_term_cycle`, `LONG_TERM_AUTO_STRATEGY` in `.env`), con
una scelta di design esplicita: il ciclo Advanced usa lo **stato** (chiusura
mensile chiusa sopra/sotto la SMA10) e non l'incrocio del mese. A regime è
la stessa cosa (dopo un incrocio dal basso il prezzo È sopra la SMA), ma lo
stato (a) definisce cosa fare su un conto nuovo, dove "dentro se già
dentro" non ha senso, e (b) si auto-ripara se il ciclo di un mese è stato
saltato — un incrocio perso non si rivede mai più, lo stato sì.

## Cosa NON è coperto da questo codice

- Le due componenti proprietarie del corso (screener "Barchart"/"ProScreener"
  preconfigurati, indicatori "Domanda/Offerta" e "PD90 Sentiment") non sono
  replicabili senza le loro formule esatte — sostituite da equivalenti
  aperti dove possibile (screening su liste di ticker via `yfinance`,
  indicatori standard)
- I sotto-indici settoriali "Dow Jones US ..." citati nel corso non sono
  liberamente disponibili: il codice usa gli **ETF settoriali SPDR** (XLK,
  XLF, XLE, ...) come proxy di settore, un'approssimazione standard e
  ampiamente usata nell'analisi tecnica USA
- Nessuna parte di questo codice o documento costituisce consulenza
  finanziaria
