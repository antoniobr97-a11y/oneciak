# Verifica del bot contro il corso

## Le trascrizioni

L'utente aveva ragione: le trascrizioni **erano state consegnate**,
incollate in chat (copiate dal pannello trascrizioni di YouTube) nella
prima sessione. Non erano su disco, quindi cercarle fra i file non le
trovava. Recuperate dal registro: **27 video, 1,2 MB**.

Materiale a pagamento: restano in locale, non vengono committate.

**La copertura della strategia è completa.** I numeri non consegnati (21,
22, 24, 26, 28, 35, 37, 42, 43) non sono buchi: la strategia si chiude da
sola. Il video 34 dice *"l'ultimo pattern di continuazione del trend"*, il
36 *"l'ultimo pattern della collana"*, il 46 è il riepilogo generale con
la checklist operativa. Ogni componente implementata nel bot ha la sua
lezione presente:

| Componente | Video |
|---|---|
| Qualificazione del trend | 27 |
| Pullback Semplice | 29 |
| Trend Knockout (TKO) | 30 |
| Pullback Persistente | 31 |
| Trend Pivot Pullback | 32 |
| Second Entry Pullback | 33 |
| Sacro Graal (pullback su EMA20) | 34 |
| Bowai | 36 |
| Analisi settoriale | 38 |
| Indicatori e volatilità | 39 |
| Screen automatici | 40 |
| Calcolo di entrata e stop | 41 |
| Money management e Profit Factor | 44 |
| Rischio percentuale e drawdown | 45 |
| Checklist operativa finale | 46 |
| Errori da non fare mai | 47 |
| Lungo termine: ETF, Harry Browne, PAC | lezioni iniziali |

**I sette pattern del codice corrispondono uno a uno ai sette del corso**
(`patterns.py`: pullback_semplice, tko, pullback_persistente,
trend_pivot_pullback, second_entry_pullback, sacro_graal, bowai).
Nessuno inventato, nessuno mancante.

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

# Parte ETF / lungo termine — verificata

## Harry Browne

| Regola del corso | Nel bot | Esito |
|---|---|---|
| Quattro parti uguali: **azioni, obbligazioni a lunga scadenza, obbligazioni a breve scadenza, oro** | `VT, TLT, SHY, GLD` | ✅ esatto |
| 25% ciascuno | `WEIGHT_PER_ASSET = 0.25` | ✅ |
| Replicato **tramite ETF** | ✅ | *"abbiamo replicato il portfolio di Harry Brown tramite l'utilizzo degli ETF"* |
| Ribilanciamento **trimestrale, semestrale o annuale** | `REBALANCE_FREQUENCY = quarterly` | ✅ dentro le tre opzioni |
| Allocazione fissa, non legata al profilo di rischio | ✅ | *"non c'è una ripartizione determinata dal proprio profilo di rischio"* |

## Portafoglio Advanced

| Regola del corso | Nel bot | Esito |
|---|---|---|
| **Una volta al mese** | ciclo mensile idempotente | ✅ |
| *"il primo giorno del mese"* | agisce al primo avvio utile del mese | ✅ più robusto: se il PC è spento l'1, recupera senza saltare il mese |
| Media mobile a **10 mesi**, time frame mensile | `ADVANCED_SMA_PERIOD = 10`, barre mensili | ✅ |
| Segnale sulla **chiusura mensile** | `closed_monthly_closes` — solo mesi CHIUSI | ✅ |
| Acquisto: prezzi sotto la media, la bucano dal basso e **chiudono sopra** | `is_above_sma` (stato sopra/sotto) | ✅ **equivalente**: comprare all'incrocio verso l'alto e vendere alla chiusura sotto significa essere investiti esattamente quando si è sopra la media |
| Vendita: chiusura mensile **sotto** la media | ✅ | |
| *"una volta costruita la propria squadra di ETF, non si cambia"* | lista fissa in configurazione | ✅ |

## PAC

Il corso lo descrive come *"un piano di azione organizzato che permette di
investire una predeterminata cifra a intervalli regolari"*. Nel bot è un
comando **manuale** (`pac` con `--deposit`), non automatico: coerente,
perché è l'utente a decidere quando e quanto versare.

## Valuta — una correzione a quello che si credeva

L'utente aveva detto che *"gli ETF devono essere italiani o hedged"*. **Il
corso non lo dice.** Dice (lezione sugli ETF):

> *"se andiamo a negoziare ETF in euro non c'è rischio cambio… se andiamo
> a negoziare ETF in valuta estera dobbiamo fare i conti con il cosiddetto
> rischio cambio, **che può essere anche un'opportunità**… se ti gioca a
> favore hai un extra rendimento… **è comunque un elemento da tenere in
> considerazione**"*

Quindi: **non è un divieto, è un fattore da sapere**. Gli ETF del bot
(VT, TLT, SHY, GLD) sono quotati in dollari, quindi il rischio cambio
euro/dollaro c'è ed è reale — può aiutare o danneggiare. Non è una
violazione del corso, ma è un'esposizione che non era mai stata scelta
consapevolmente. Resta una decisione aperta per l'utente, non una
correzione da fare al codice.

---

# Lettura integrale dei video chiave (non solo ricerca per argomenti)

La verifica precedente era fatta **cercando**: si interroga il testo su
quello che si sospetta e si legge il passaggio. Cercare trova solo quello
che si sospetta già. Leggere trova quello che non si sapeva di cercare.
Questi video sono stati letti per intero.

## Video 41 — il calcolo di entrata e stop (il più operativo di tutti)

La formula esatta del corso:

> entrata long = **chiusura della barra di setup + volatilità**
> stop long = **minimo della barra di setup − volatilità**
> *"può succedere che a causa dell'ampio range della barra di setup ti
> cada dentro. Se cade dentro, dobbiamo necessariamente spostarlo comunque
> sopra il massimo della barra"*

Il codice (`levels.py:compute_levels`):

```python
entry = setup_bar["close"] + volatility
if entry <= setup_bar["high"]:
    entry = setup_bar["high"] + 0.01
stop_loss = stop_bar["low"] - volatility
```

**Esatto, caso particolare compreso.** Lo short è speculare, come nel
corso. La barra di setup è quella col minimo più basso del pullback
(massimo più alto per gli short): confermato.

Il motivo della formula, con le parole del corso: *"per evitare di essere
eseguiti soltanto dal semplice rumore di fondo del titolo"*.

## Video 39 — gli indicatori

| Indicatore | Corso | Nel bot |
|---|---|---|
| MACD | **settimanale**, 12/26/9 | ✅ `macd(fast=12, slow=26, signal=9)` su barre settimanali |
| ADX | **giornaliero, 14 periodi** | ✅ `adx_qualifier(df, period=14)` |
| Medie mobili multiple | **esponenziali**, brevi **3/5/8/10/12/15**, lunghe **30/35/40/45/50/60**, giornaliero | ✅ identico in `ema_ribbon` |

Nota: la ricerca per parola chiave non le aveva trovate perché il corso
non dice mai "ribbon" né "nastro": dice *"medie mobili multiple"* e
*"fascio di medie"*. È esattamente il tipo di cosa che solo la lettura
integrale trova.

## La divergenza più profonda, che non è un parametro

Video 39, ripetuto tre volte con parole diverse:

> *"gli indicatori vanno a supporto dell'investitore, **non lo devono
> sostituire**, cioè la **decisione finale spetterà sempre
> all'investitore** se andare a negoziare o meno un determinato strumento
> finanziario"*

> *"non prendere mai, e ripeto mai, una decisione operativa sulla base del
> solo indicatore"*

Il corso è costruito attorno a un investitore che **guarda e decide**. Gli
indicatori sono conferme di un'analisi visiva già fatta a occhio, non
sostituti di quell'analisi.

Un bot automatico **rimuove quella persona**. Non è una regola violata --
non esiste una riga del corso che vieti di automatizzare, il corso non si
pone il problema -- ma è la differenza vera fra il metodo insegnato e
quello che gira ogni sera, e conta più di qualunque soglia numerica.

Va detto anche il rovescio, che è a favore dell'automazione: il corso
avverte che *"la soggettività è nemica dell'investitore"* e dedica il
video 47 alle cose da non fare mai, che sono tutte cedimenti umani
(spostare lo stop, investire sul sentito dire, operare senza stop). Il bot
quei cedimenti non li ha. Toglie il giudizio buono insieme a quello
cattivo.

---

# ESTRAZIONE MECCANICA COMPLETA — tutti e 27 i video

Le verifiche precedenti cercavano per argomento, e cercare trova solo ciò
che si sospetta. Per chiudere il buco sono state estratte
**meccanicamente 703 affermazioni numeriche uniche** da tutti e 27 i
video — ogni numero accompagnato da un'unità operativa (periodi, barre,
mesi, %, scambi) o da una parola-parametro — e lette tutte.

Questo è l'elenco completo dei parametri del corso e del loro esito.

## Qualificazione del trend — tutti e sei, con la loro definizione

> *"performance, gap, range, massimi e minimi, la DX e la persistenza
> sono **i sei principali qualificatori di trend**"* (video 27)

| Qualificatore | Corso | Codice | |
|---|---|---|---|
| Performance | ≥ **+30%** (o ≤ −30%) negli ultimi **2-3 mesi** | 30%, 60 giorni | ✅ |
| Gap | in direzione del trend | `gap_qualifier` | ✅ |
| Range | barre ampie **con chiusura nel 25% superiore/inferiore** | `close_position >= 0.75` | ✅ |
| Massimi/minimi | armonia, crescenti o decrescenti | `harmony_qualifier` | ✅ |
| ADX | **14 periodi**, sopra **30**, crescente | `period=14`, soglia 30 | ✅ |
| Persistenza | almeno **20 barre** | 20 | ✅ |
| Quanti servono | *"difficilmente ci saranno tutti e sei… già se riesci a identificarne **due o tre**"* | `TREND_MIN_QUALIFIERS=2` | ✅ |

## I sette pattern e i loro numeri esatti

| Pattern | Video | Numeri del corso | |
|---|---|---|---|
| Pullback Semplice | 29 | massimo di **2-3 mesi**; ritracciamento **min 2, max 7 barre** (*"oltre le sette il segnale si annulla"*) | ✅ |
| Trend Knockout | 30 | sellof che rompe **2-3 minimi** precedenti | ✅ |
| Pullback Persistente | 31 | persistenza **≥20 barre**, poi pullback 2-7 | ✅ |
| Trend Pivot Pullback | 32 | ritracciamento **da 2 a 5 barre, non sette** | ✅ |
| Second Entry Pullback | 33 | **da 2 a 5 barre** | ✅ |
| Sacro Graal | 34 | pullback che tocca la **EMA 20**; entrata sopra il massimo della barra che l'ha toccata | ✅ |
| Bowai | 36 | estremo di **almeno 6 mesi** (non 2-3); inversione **entro 5 giorni**; medie **SMA10 / EMA20 / EMA30** allineate | ✅ |

Stop: *"qualsiasi pattern tu vada ad analizzare… lo stop loss va **sotto
al minimo della barra di setup**"* (video 34) — ✅ in tutti e sette.

## Indicatori — tutti e cinque

| Indicatore | Corso | Codice | |
|---|---|---|---|
| MACD | **settimanale**, 12/26/9 — *"l'unico che si osserva sul settimanale"* | ✅ | ✅ |
| ADX | giornaliero, **14 periodi** | ✅ | ✅ |
| Medie mobili multiple | **esponenziali**: 3/5/8/10/12/15 e 30/35/40/45/50/60 | identiche | ✅ |
| Estensione media giornaliera | *"intorno ai **10 periodi**"* — usata per entrata e stop | `VOLATILITY_PERIOD=10` | ✅ |
| Historical Volatility | **20 periodi**; *"titoli che abbiano historical volatility **superiore al settore, e superiore il settore al mercato**"* | `hv_stock > hv_sector > hv_market`, periodo 20 | ✅ |

## Entrata, stop e gestione

| Regola | Corso | |
|---|---|---|
| Entrata long | chiusura barra di setup **+ volatilità** | ✅ |
| Se cade dentro la barra | spostare **sopra il massimo** | ✅ |
| Stop long | minimo **− volatilità** | ✅ |
| A 1R | vendi metà, stop a pareggio | ✅ |
| A 3R/4R | *"puoi optare per chiudere l'intera posizione o gran parte"* | ⚠️ il bot ne lascia correre il 20% |
| Residuo | esce sotto la media **200 o 100** | ✅ |
| Mai senza stop | *"non si apre mai un'operazione senza stop loss"* | ✅ auto-riparazione |
| Mai abbassare lo stop | *"mai spostare lo stop loss **in difetto**"* | ✅ |

## Universo, settore, rischio, ETF

Volume ≥ **100.000** scambi medi ✅ · forza relativa titolo/settore/mercato
✅ · conferma settoriale **obbligatoria per il Bowai** (`screener.py:299`)
✅ · rischio **1%** per operazione (tetto del corso per chi inizia) ✅ ·
Harry Browne quattro asset al 25% ✅ · ribilanciamento trimestrale (il
corso ammette 3/4/6/12 mesi) ✅ · Advanced media **10 mesi** su chiusura
mensile ✅ · PAC manuale ✅.

---

# LE DUE UNICHE COSE NON IMPLEMENTATE

Su 703 affermazioni numeriche, dopo tutte le verifiche, restano due
scostamenti — entrambi minori, entrambi ora dichiarati.

**1. Le barre ad ampio range andrebbero pesate di più se recenti.**
> *"La cosa fondamentale è trovare barre ad ampio range, **meglio ancora
> nella seconda metà del periodo** che stiamo analizzando"* (video 27)

Il codice le conta ovunque nella finestra, senza preferenza per la parte
destra del grafico. Il corso dice che contano di più quelle vicine a oggi,
*"perché noi operiamo dalla parte destra del grafico"*.

**2. L'indicatore Domanda/Offerta non esiste nel bot.**
Il corso lo cita fra gli indicatori (settaggio 14 periodi), ma è un
indicatore proprietario di ProRealTime: non è ricostruibile dai dati
pubblici di prezzo e volume che il bot scarica. Non è una svista, è un
limite dei dati disponibili — ma va scritto.

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

- Il PAC e le regole ETF non sono ancora stati confrontati riga per riga:
  la verifica si è concentrata sulla parte azionaria, che è quella che
  opera ogni giorno.
