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

## Valuta degli ETF — ERRORE MIO, l'utente aveva ragione

**Cosa era stato scritto qui il 14 settembre:** *"L'utente aveva detto che
gli ETF devono essere italiani o hedged. **Il corso non lo dice.**"*

**È falso. Il corso lo dice, ed è esplicito.** Trovato dopo che l'utente ha
mandato le sue note scritte a mano, che costringevano a ricontrollare:

> *"La valuta in genere noi, soprattutto **per portafogli statici**, cioè
> che si costruiscono e si lasciano andare così nel tempo, **si predilige
> ETF in valuta euro oppure hedgiati**"*

E, parlando direttamente di Harry Browne:

> *"su un Harry Brown che dura anni e resti sempre investito sullo stesso
> strumento finanziario, **noi ad esempio abbiamo tutti strumenti in euro
> comunque hedgiati**. Mentre per quanto riguarda la strategia
> **advanced**, entrando ed uscendo sul mercato con maggiore rapidità,
> abbiamo anche prodotti **ad esempio in dollari**"*

Il motivo, dal corso: *"il rischio cambio **aumenta all'aumentare del
tempo** che detengo l'investimento"*.

La regola vera è quindi più fine di come l'aveva posta l'utente e molto
diversa da come l'avevo negata io:

| Portafoglio | Orizzonte | Valuta secondo il corso |
|---|---|---|
| **Harry Browne** | anni, mai toccato | **euro o hedged** |
| **Advanced** | dentro/fuori ogni mese | **anche dollari** |

**Perché l'errore.** I sottotitoli automatici di YouTube scrivono
"hedgiati" come **"e giati"** e **"egiati"**. La ricerca su "hedg" non
trovava nulla, e la riga *"focalizzare la propria attenzione su ETF e
giati"* era passata sotto gli occhi senza essere riconosciuta. È
esattamente il limite della fonte dichiarato in cima a questo documento —
solo che a caderci è stato chi l'aveva dichiarato.

### Cosa comporta, e perché non si corregge nel codice

Il bot usa `VT, TLT, SHY, GLD` per Harry Browne: **tutti quotati negli
USA, in dollari, nessuno con copertura valutaria.** Il portafoglio che
secondo il corso deve stare in euro o hedged è interamente in dollari, ed
è proprio quello destinato a restare fermo per anni — il caso in cui il
corso dice che il rischio cambio pesa di più.

**Non è una riga da cambiare.** Alpaca negozia solo su NYSE, NASDAQ, ARCA,
AMEX e BATS (`_ALLOWED_EXCHANGES`). Gli ETF UCITS in euro o hedged sono
quotati su Borsa Italiana, Xetra, Euronext: **Alpaca non può comprarli**,
qualunque ticker si metta in configurazione.

Quindi la parte ETF della strategia, su questo broker, **non può seguire
il corso**. È una scelta di infrastruttura, non di codice, e va presa
dall'utente:

1. **Tenere gli ETF su Alpaca in dollari**, sapendo che si assume il
   rischio cambio su un investimento pluriennale — proprio quello che il
   corso sconsiglia.
2. **Spostare la parte ETF su un broker europeo** e comprare gli UCITS
   hedged a mano. Il bot continua a dire *cosa* comprare e *quando*
   ribilanciare (`bot.py long-term-status`), l'esecuzione la fa la persona.
3. **Togliere gli ETF dal bot** e gestirli separatamente.

La parte azionaria (breve termine) non è toccata: il corso la vuole su
azioni USA, e lì il dollaro è inevitabile.

## PD90 Sentiment — la regola c'è, la formula no

Le note dell'utente riportano l'indicatore che qui era segnato come "non
implementato":

> *"PD90 SENTIMENT → ci sono i BIG (blu) e i SMALL investitori (rosso).
> **Dobbiamo operare quando i BIG sono superiori degli SMALL**"*
> *"DOMANDA − OFFERTA → devo avere più domanda, **verde sopra al rosso**"*

Il video 30 conferma il concetto: *"i grossi investitori sono in genere
identificati come big investor oppure **mani forti**… è opportuno, quando
investiamo, essere nella stessa direzione in cui si trovano le mani
forti"*.

**Ora si sa cosa dovrebbe fare, ma non come si calcola.** È un indicatore
proprietario di ProRealTime: non è ricostruibile dai dati di prezzo e
volume che il bot scarica. Resta non implementato, ma adesso è documentato
come *regola nota e non calcolabile*, non come lacuna generica.

## Entrata e stop — riconfermati dalle note

Le note riportano la stessa formula già verificata nel video 41:

> *"il livello di entrata si fa sommando **volatilità + chiusura** di quel
> giorno → entry level"*
> *"il livello di uscita si fa **min. barra di setup − volatilità** → stop
> loss"*

Identico al codice (`levels.py:compute_levels`).

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

# Appunti vecchi contro trascrizioni attuali

L'utente ha caricato i suoi appunti scritti a mano del corso, poi ha
chiarito: *"questi erano dei miei appunti del corso di tanto tempo fa,
infatti il corso l'ho ripreso dopo anni, quindi non guardare il numero di
lezione se coincide con le trascrizioni che ti ho mandato"*.

**Regola adottata: dove appunti e trascrizioni divergono, vince la
trascrizione.** Gli appunti descrivono una versione precedente del corso.
Il bot deve seguire la versione che l'utente sta studiando oggi, cioè le
27 trascrizioni.

Le cinque divergenze, riverificate una per una contro le trascrizioni
attuali:

**1. Obbligazioni / TLT.** Gli appunti indicano scadenze diverse. Le
trascrizioni dicono: *"scadenza minimo di 7-10 anni… a noi interessa
7-10, 10+ per il lungo periodo"*. TLT (20+) rientra esplicitamente nel
"10+". **Non è un errore, niente da cambiare.**

**2. Super Trend.** Presente negli appunti. **Assente da tutte e 27 le
trascrizioni.** Appartiene alla versione vecchia del corso. **Non va
implementato.**

**3. Ritracciamento al 50% del range.** Presente negli appunti. Assente
dalle trascrizioni: il corso attuale parla del **25% superiore**, che è
esattamente quello che fa il codice. **Niente da cambiare.**

**4. Inside bar escluse dal conteggio del pullback.** Questa regola degli
appunti è confermata anche dal corso attuale — video 29: *"Queste non si
conteggiano all'interno del nostro pullback"*. Ma era **già
implementata**: `patterns.py` ha `_is_inside_bar`, `_pullback_segment`
restituisce `non_inside` e `detect_pullback_semplice` conta solo quelle.
**Niente da cambiare.**

**5. Sacro Graal, "toccare la media senza superarla".** Il "senza
superarla" è negli appunti ma non nel corso attuale: il video 34 dice
soltanto *"andare a toccare la media mobile esponenziale a 20 periodi"*.
**Niente da cambiare.**

**Esito: zero modifiche al bot.** Gli appunti vecchi avevano suggerito
quattro interventi; riverificati contro il corso attuale, nessuno regge.

---

# Ancora da fare

- Il PAC e le regole ETF non sono ancora stati confrontati riga per riga:
  la verifica si è concentrata sulla parte azionaria, che è quella che
  opera ogni giorno.
