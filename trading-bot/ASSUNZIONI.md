# Inventario delle assunzioni

Questo documento esiste per un motivo preciso. Finora ogni volta che si
chiedeva "come si migliora?", saltava fuori qualcosa di tralasciato — e
questo significa che non era mai stato fatto un **inventario**: si
rispondeva alle domande invece di enumerare lo spazio delle risposte.

Qui c'è **ogni** numero che il bot usa per decidere, con tre informazioni:
da dove viene, se è stato misurato, e cosa succede se è sbagliato.

Il punto non è che tutto sia verificato. Il punto è che **niente sia
invisibile**.

Totale: **66 parametri** — 48 configurabili in `.env`, 18 costanti scritte
nel codice (quelle che non si vedrebbero mai guardando la configurazione).

---

## Legenda

| Simbolo | Significato |
|---|---|
| **M** | **Misurato**: esiste un backtest che confronta questo valore con almeno un'alternativa |
| **C** | **Corso**: numero dichiarato esplicitamente dal corso |
| **L** | **Letteratura**: convenzione standard di analisi tecnica, presa da fonti esterne |
| **S** | **Scelta**: l'ho deciso io. Ragionevole, motivato, **mai verificato sui dati** |
| **T** | **Tecnico**: non influenza le decisioni di trading (timeout, percorsi file, retry) |

---

## 1. Money management — il gruppo più importante

Questi decidono quanto si rischia. Sono anche i più testati, perché sono
quelli che contano di più.

| Parametro | Valore | | Note |
|---|---|---|---|
| `SHORT_TERM_RISK_PER_TRADE_PCT` | 1.0 | **M** | Testato 0,25 / 0,5 / 1 / 2. Altopiano, non scogliera. Sharpe identico a 0,5% con drawdown migliore |
| `SHORT_TERM_MAX_AGGREGATE_RISK_PCT` | 12.0 | **M** | Testato contro 6. A 6 lo Sharpe peggiora (0,92 contro 1,00) |
| `SHORT_TERM_MAX_PER_SECTOR` | 3 | **M** | Testato contro nessun limite. **Unica modifica che migliora rendimento E drawdown insieme** |
| `SHORT_TERM_CAPITAL` / `LONG_TERM_CAPITAL` | 10.000 / 10.000 | **M** | Il mix 50/50 misurato su 18 anni. Netto tasse l'ottimo è 40/60, ma la curva è piatta fra i due |
| `SHORT_TERM_MAX_DRAWDOWN_PCT` | 0 (spento) | **M** | Acceso era una trappola senza uscita (backtest v8b). Spento deliberatamente |
| `SECOND_SCALE_OUT_R` | 3.0 | **S** | *Costante nel codice.* Il corso dice "intorno a 3R/4R": 3 scelto, 4 mai provato |
| `SECOND_SCALE_OUT_FRACTION` | 0.30 | **S** | *Costante nel codice.* Mai confrontata con altre ripartizioni |
| `RUNNER_FRACTION` | 0.20 | **S** | *Costante nel codice.* Mai confrontata |

**Il buco qui:** la scala di uscita (metà a 1R, 30% a 3R, 20% corre) non è
mai stata confrontata con nessuna alternativa. È presa dal corso come
struttura, ma le tre frazioni precise sono mie.

---

## 2. Qualificazione del trend — 6 filtri, 4 mai misurati

| Parametro | Valore | | Note |
|---|---|---|---|
| `TREND_MIN_QUALIFIERS` | 2 | **C** | Corso: "ne bastano 2-3 su 6". Scelto il minimo. **Con 2 qualifica l'87% dei titoli** (visto dal vivo): filtra pochissimo |
| `TREND_LOOKBACK_DAYS` | 60 | **C** | Corso: "ultimi 2-3 mesi" |
| `TREND_ADX_THRESHOLD` | 30.0 | **L** | Convenzione standard ADX (>25 trend, >30 forte) |
| `MARKET_REGIME_MA_PERIOD` | 200 | **L** | La media più usata al mondo per distinguere toro/orso |
| `MARKET_REGIME_FILTER` | True | **M** | Testato acceso/spento (v5) |
| `TREND_PERFORMANCE_THRESHOLD_PCT` | 30.0 | **S** | **Mai misurato.** Perché 30% e non 20 o 40? Nessuna ragione forte |
| `TREND_PERSISTENCE_WINDOW` | 20 | **S** | **Mai misurato** |
| `PERSISTENCE_TOLERANCE_ATR_MULT` | 1.0 | **S** | *Costante nel codice.* **Mai misurato** |
| `WIDE_RANGE_ATR_MULT` | 1.5 | **S** | **Mai misurato** |
| `WIDE_RANGE_MIN_COUNT` | 2 | **S** | *Costante nel codice.* **Mai misurato** |
| `GAP_VOLATILITY_MULT` | 0.5 | **S** | **Mai misurato** |
| `RIBBON_MIN_SEPARATION_PCT` | 0.3 | **S** | **Mai misurato** |
| `VOLATILITY_PERIOD` | 10 | **C** | Corso, "Indicatore di Volatilità" |

**Il buco qui è il più grande:** 7 soglie su 13 sono scelte mie mai
verificate. Il corso non dava numeri ("gap", "barra ad ampio range" sono
giudizi visivi sul grafico) e ho messo convenzioni ragionevoli. Ragionevoli
non vuol dire giuste.

---

## 3. Pattern

| Parametro | Valore | | Note |
|---|---|---|---|
| `PULLBACK_REQUIRE_LOWS` | True | **M** | Testato (v10): versione fedele al corso |
| `BOWAI_EXTREME_LOOKBACK` | 126 | **C** | *Costante.* Corso: "minimo di almeno 6 mesi" |
| `BOWAI_INVERSION_WINDOW` | 5 | **C** | *Costante.* Corso: "inverte in <=5 giorni" |
| Formula Sacro Graal | restrittiva | **M** | La versione fedele alla lettera è stata misurata e **rende meno** (102.349 contro 120.214). Documentato accanto al codice |

---

## 4. Filtri di rischio — misurati, e bocciati come veti

| Parametro | Valore | | Note |
|---|---|---|---|
| `SUPPORT_RESISTANCE_MIN_R_MULTIPLE` | 3.0 | **M** | Come **veto** distrugge la strategia (7,12% → 0,89% fuori campione). Resta un avviso |
| `SECTOR_RS_LOOKBACK_DAYS` | 60 | **S** | **Mai misurato** |
| `EARNINGS_WARNING_DAYS` | 15 | **S** | **Mai misurato** |
| `SHORT_MIN_PRICE` | 80.0 | **C** | Corso: short preferibili sopra $80-100. Irrilevante: gli short sono spenti |
| `SHORT_TERM_ALLOW_SHORTS` | False | **M** | Gli short sono in perdita netta in **ogni** versione testata |

---

## 5. Universo

| Parametro | Valore | | Note |
|---|---|---|---|
| `SHORT_TERM_USE_FULL_MARKET` | True | **M** | Scansiona tutto il mercato |
| `SHORT_TERM_FULL_MARKET_MAX_SYMBOLS` | 300 | **M** | Allargare a 188 titoli nel backtest **non** migliora (drawdown peggiore) |
| `SHORT_TERM_MIN_ANNUALIZED_VOLATILITY_PCT` | 25.0 | **M~** | Motivato dal backtest v4, ma il valore 25 non è mai stato confrontato con 20 o 30 |
| `SHORT_TERM_MIN_PRICE_FULL_MARKET` | 10.0 | **S** | **Mai misurato** |
| `SHORT_TERM_MIN_DOLLAR_VOLUME` | 5.000.000 | **S** | **Mai misurato** |
| `SHORT_TERM_MIN_SHARE_VOLUME` | 100.000 | **C** | Corso, video 18 |
| `MIN_HISTORY_BARS` | 250 | **S** | *Costante.* Ragionata (SMA200 + 52 settimane), mai misurata |
| `SHORT_TERM_PENDING_MAX_DAYS` | 20 | **S** | **Mai misurato** |

---

## 6. Lungo termine (ETF)

| Parametro | Valore | | Note |
|---|---|---|---|
| `LONG_TERM_AUTO_STRATEGY` | harry_browne | **M** | Harry Browne batte Advanced su rendimento e Sharpe |
| `HARRY_BROWNE_TICKERS` | VT,TLT,SHY,GLD | **⚠** | **Vedi sezione 8: sono tutti in dollari, contro quanto dice il corso** |
| `REBALANCE_FREQUENCY` | quarterly | **S** | **Mai misurato.** Semestrale e annuale non provati. Il corso dice "capitali grandi ribilanciano più spesso" |
| `ADVANCED_SMA_PERIOD` | 10 | **C** | Corso |
| `ADVANCED_BOND_LONG_SPLIT` | 0.5 | **S** | Il corso non lo specifica. Mai misurato |
| `LONG_TERM_RISK_SCORE` | 25 | **?** | **Il questionario non è mai stato compilato davvero.** 25 = "medio", messo come default |

---

## 7. Tecnici — non toccano le decisioni di trading

`ALPACA_*`, `RUN_TIME`, `ALERT_WEBHOOK_URL`, `POSITION_STATE_PATH`,
`SYMBOL_CACHE_*`, `HTTP_*`, `MIN_VOLATILITY_COVERAGE`,
`MIN_LIQUIDITY_COVERAGE`, `MAX_SCAN_FAILURE_RATE`, `EQUITY_HISTORY_DAYS`,
`LONG_TERM_MA_PERIOD` (uscita runner). Tutti **T**.

---

## 8. Fuori dal codice: i tre problemi strutturali

Non sono parametri. Sono scelte di impianto, e pesano più di qualunque
soglia.

### 8.1 Gli ETF sono in dollari, e il corso dice il contrario

Il corso raccomanda esplicitamente, per il lungo termine, strumenti **"in
EUR o hedged"**. I quattro ETF configurati (VT, TLT, SHY, GLD) sono tutti
americani, in dollari.

**Non è una svista rimediabile cambiando i ticker.** Alpaca è un broker
USA: negozia strumenti quotati negli Stati Uniti. Gli ETF UCITS
europei — quelli armonizzati, in euro o con copertura valutaria — sono
quotati sulle borse europee. **Alpaca non può comprarli.**

C'è quindi un conflitto vero fra "automatizzare tutto su Alpaca" e "seguire
il corso sulla valuta".

Tre strade, con i loro costi:

| | Come | Costo |
|---|---|---|
| **A. Lasciare com'è** | ETF USA su Alpaca | rischio cambio pieno; complicazioni fiscali USA da verificare |
| **B. Spostare gli ETF** | broker italiano, ETF UCITS EUR/hedged, **a mano** | il bot non li gestisce più — ma sono **4 operazioni ogni 3 mesi**, non serve un bot |
| **C. Solo azioni sul bot** | Alpaca per il breve termine, ETF altrove | come B, ma è la divisione naturale |

**La B/C è probabilmente la risposta giusta**, e per una ragione che non
c'entra col cambio: su un broker italiano in regime amministrato le tasse
te le trattiene il broker, niente quadro RW, niente calcoli. E il
portafoglio ETF è talmente statico che automatizzarlo non porta nessun
vantaggio.

**Da verificare con un commercialista prima di usare denaro vero** —
non sono un consulente fiscale e su questo non voglio che ti fidi di me.

### 8.2 Survivorship bias

Vedi STRATEGY.md, "I limiti dei numeri di questo documento". I 210 titoli
del backtest sono tutti sopravvissuti: i numeri sono un tetto, non una
previsione.

### 8.3 Le tasse

Vedi la stessa sezione. Il breve termine paga in tasse più del capitale
iniziale su 18 anni; il mix ottimo netto si sposta verso gli ETF.

---

## 9. Il conto onesto

| | Quanti |
|---|---|
| Parametri totali | 66 |
| Tecnici (non decidono nulla) | 18 |
| **Che influenzano le decisioni** | **48** |
| di cui **misurati** (M) | 16 |
| di cui **dal corso** (C) | 10 |
| di cui **da letteratura** (L) | 3 |
| di cui **scelti da me, mai verificati** (S) | **18** |
| non determinati (questionario mai fatto) | 1 |

**Diciotto parametri su 48 sono scelte mie mai messe alla prova.** Questo è
il numero che risponde alla domanda "perché continua a saltare fuori
qualcosa".

### Cosa NON si farà con questa lista

Non si misureranno tutti e 18 cercando il valore migliore. Diciotto
parametri con tre valori ciascuno fanno 387 milioni di combinazioni: con
abbastanza tentativi **qualcosa sembra sempre buono per caso**, ed è così
che un backtest smette di dire la verità.

### Cosa si farà

Un **test di sensibilità**, che è una domanda diversa: non *"quale valore
vince?"* ma *"il risultato regge se sposto questo numero?"*.

Si muove un parametro alla volta di ±30% e si guarda se il risultato
resta nello stesso quartiere. Se regge, il valore preciso non conta e la
strategia è solida. Se crolla, quel parametro è un punto fragile e va
saputo — **anche se il valore attuale è quello che rende di più.**

La differenza è tutta qui: la sensibilità cerca la fragilità, non il
massimo.
