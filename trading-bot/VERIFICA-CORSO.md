# Verifica del bot contro il corso

## Le trascrizioni

L'utente aveva ragione: le trascrizioni **erano state consegnate**,
incollate in chat (copiate dal pannello trascrizioni di YouTube) nella
prima sessione. Non erano su disco, quindi cercarle fra i file non le
trovava. Recuperate dal registro: **27 video, 1,2 MB**.

Materiale a pagamento: restano in locale, non vengono committate.

**Mancano** i video 21, 22, 24, 26, 28, 35, 37, 42, 43. Tutto quanto segue
vale per i 27 recuperati.

**Avvertenza sulla fonte.** Sono sottotitoli automatici di YouTube, con
errori: *"votai"* per Bowai, *"AD"/"DX"* per ADX, *"Drwdrown"* per
drawdown, *"Harry Brown"*. Sulle parole il contesto salva; **sui numeri
no**. Un numero mal trascritto non è distinguibile da uno giusto.

---

# ERRORE 1 (grave) — il corso raccomanda lo 0,5% a chi inizia

**Video 45, testuale:**

> *"in genere si tende a non rischiare più dell'1-2% per singola
> operazione, **ma all'inizio è ancora meno, cioè all'inizio che ti
> avvicini in questo ambiente non rischiare oltre lo 0,5, al massimo l'1%
> per operazione. Tienilo basso**"*

Il bot rischia l'1%: è dentro le regole, è il tetto. Ma il corso
raccomanda **0,5% a chi comincia**, e questo non era mai stato riferito.

Il 14 settembre all'utente è stata proposta esattamente la scelta fra 1% e
0,5% con le tabelle del backtest, e ha scelto 1% **senza sapere che il
corso consiglia 0,5% a chi è all'inizio**. La scelta va rifatta con
l'informazione davanti.

Le due fonti concordano: il backtest dice che a 0,5% il drawdown scende da
−17,2% a −14,1% con Sharpe identico. Il corso dice *"tienilo basso"*.

**DECISIONE (14 settembre 2026): l'utente conferma l'1%**, questa volta con
la citazione del corso davanti. Non è una violazione: la frase è *"non
rischiare oltre lo 0,5, **al massimo l'1%**"*, quindi l'1% è il tetto che
il corso concede a chi inizia, e il bot ci sta esattamente sopra, non
oltre. Questione chiusa: non va riaperta senza un motivo nuovo.

# ERRORE 2 — il trailing stop NON contraddiceva il corso

Il 13 settembre il trailing è stato spento per due motivi. Il secondo era
*"contraddice il corso, che dice di lasciare lo stop fermo al pareggio"*.

**Falso. Video 47:**

> *"Una cosa da non fare mai, e ripeto mai, è spostare lo stop loss **in
> difetto** dopo aver aperto l'operazione"*

Vieta di **abbassarlo**, non di alzarlo. Il trailing implementato alzava
soltanto — *"lo stop non scende MAI"* era la sua proprietà centrale, con
un test dedicato.

**La prima motivazione resta valida e decisiva**: fuori campione il
trailing vince in 8 anni su 16. La decisione di tenerlo spento non cambia.
Ma era stata presentata come basata su due ragioni, e una non esisteva.

# ERRORE 3 (minore) — il tetto aggregato

Il bot usa 12% (12 posizioni × 1%). L'esempio del corso (video 45) è
**10 operazioni = 10%**. Il 12 non compare: è stato scelto e poi misurato.

---

# Verificato CORRETTO — il grosso del bot è fedele

## Qualificazione del trend (video 27)

| Regola | Nel bot | Citazione |
|---|---|---|
| Sei qualificatori, **non serve che ci siano tutti** | `TREND_MIN_QUALIFIERS=2` ✅ | *"difficilmente ci saranno tutti e sei… già se riesci a identificarne **due o tre**"* |
| Performance ≥ 30% negli ultimi 2-3 mesi | 30%, 60 giorni ✅ | *"perlomeno si sia mosso di un 30%… negli ultimi 2-3 mesi"* |
| Barre ad ampio range **con chiusura nel 25% superiore** | `close_position >= 0.75` ✅ | *"barre ad ampio range con chiusura nel 25% superiore… della barra stessa"* |
| Gap in direzione del trend | ✅ | *"l'importante è che il gap sia in direzione del trend dominante"* |
| Massimi e minimi crescenti | ✅ | video 27 |
| Persistenza ≥ 20 barre | 20 ✅ | *"persistenza almeno 20 barre… circa un mese di borsa"* (video 31) |

## Pattern

| Regola | Nel bot | Fonte |
|---|---|---|
| Massimo importante di almeno **2-3 mesi** | ✅ | video 30/31/32/33/34 |
| Pullback semplice: **min 2, max 7 barre** | ✅ | *"oltre le sette barre il segnale si annulla"* (video 31) |
| Pivot e Second Entry: **2-5 barre**, non 7 | ✅ | video 32, 33 |
| Pullback con **massimi e minimi decrescenti** | ✅ | video 31 |
| Stop **sotto il minimo della barra di setup** | ✅ | video 31 |
| Pullback su EMA20: entrata sopra il massimo della barra che tocca la media | ✅ | video 34 |
| ADX **> 30 e crescente** | 30 ✅ | video 34 |
| Trend Knockout: sellof che rompe 2-3 minimi precedenti | ✅ | video 30 |

## Gestione dell'operazione (video 47)

| Regola | Nel bot |
|---|---|
| Mai un'operazione senza stop loss | ✅ auto-riparazione dello stop a ogni ciclo |
| A 1R: vendi metà, stop a pareggio | ✅ *"venderai metà titoli e porterai lo stop loss a pareggio"* |
| A 3R/4R: chiudi | ⚠️ vedi sotto |
| Il residuo esce sotto la media a **200 o 100** | ✅ SMA200 |

## Universo e settori

| Regola | Nel bot | Fonte |
|---|---|---|
| Volume ≥ ~100.000 scambi/giorno | 100.000 ✅ | *"focalizzati intorno ad almeno i 100.000 volumi medi giornalieri"* |
| Il settore **idealmente** stesso pattern, non obbligatorio | ✅ avviso, non veto | video 38 |
| Nel Bowai il settore è **molto importante** | ✅ `screener.py:299` scarta il Bowai senza conferma settoriale | *"nel Bowai è molto importante che si presenti anche sul settore"* |
| Forza relativa titolo/settore/mercato | ✅ | video 46 |

---

# Divergenze da decidere

**1. A 3R il corso è più aggressivo del bot.** Video 47: *"lì puoi optare
per chiudere **l'intera posizione** o comunque chiudere gran parte dei
titoli"*. Il bot vende il 30% e lascia correre il 20%. Il corso permette
entrambe le cose (*"se invece valuti di lasciar correre ancora"*), quindi
non è una violazione — ma la via del bot è la più aggressiva delle due.

**2. Gli short sono spenti.** Il corso li insegna (una lezione intera) e
li prevede su ogni pattern. Sono stati disattivati perché in perdita netta
in ogni backtest. È la deviazione più grande dal corso, presa
deliberatamente e documentata.

**3. Il filtro sull'S&P 500 (SMA200).** Video 46 dice *"idealmente anche
il mercato deve essere in trend"* — **idealmente**, non obbligatorio. Il
bot lo tratta come un veto assoluto. Più severo del corso.

---

# Ancora da fare

- I video 21, 22, 24, 26, 28, 35, 37, 42, 43 non sono disponibili
- Il PAC e le regole ETF non sono ancora stati confrontati riga per riga
