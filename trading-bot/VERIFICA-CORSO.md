# Verifica contro il corso — prima passata

## Le trascrizioni sono state recuperate

L'utente aveva ragione: le trascrizioni del corso ("Prendo il Controllo
Advanced", Gabriele Cortigiani) **erano state consegnate**, incollate in
chat nella prima sessione. Non erano su disco, quindi cercarle fra i file
non le trovava. Sono state estratte dal registro della conversazione:
**27 video, 1,2 MB di testo**.

Sono materiale a pagamento: restano in locale, **non vengono committate**.

### Cosa c'è e cosa manca

Video numerati presenti: 19, 20, 23, 25, 27, 29, 30, 31, 32, 33, 34, 36,
38, 39, 40, 41, 44, 45, 46, 47 — più 7 lezioni iniziali senza numero
(base del guadagno, lungo periodo, ETF, portafoglio, PAC, short selling).

**Mancano** i video 21, 22, 24, 26, 28, 35, 37, 42, 43. Le conclusioni qui
sotto valgono per quello che c'è.

---

## ERRORE 1 — grave: il corso dice 0,5% per chi inizia

**Il corso, video 45, parole sue:**

> *"in genere si tende a non rischiare più dell'1-2% per singola
> operazione, **ma all'inizio è ancora meno, cioè all'inizio che ti
> avvicini in questo ambiente non rischiare oltre lo 0,5, al massimo l'1%
> per operazione. Tienilo basso**"*

Il bot rischia l'1%. Non è fuori dalle regole — è il tetto — ma il corso
raccomanda **0,5% a chi comincia**, e questa raccomandazione non era mai
stata riportata all'utente.

Il 14 settembre gli è stata proposta esattamente la scelta fra 1% e 0,5%,
con le tabelle del backtest, e ha scelto 1%. **Ha scelto senza sapere che
il corso consiglia 0,5% a chi è all'inizio.** La scelta va rifatta con
questa informazione davanti.

Da notare che le due fonti concordano: il backtest dice che a 0,5% il
drawdown scende da −17,2% a −14,1% con Sharpe identico. Il corso dice la
stessa cosa in parole: *"tienilo basso"*.

---

## ERRORE 2 — il trailing stop NON contraddice il corso

Il 13 settembre il trailing stop è stato spento con due motivazioni. La
seconda era: *"è una modifica contro il corso, che dice di lasciare lo
stop fermo al pareggio"*.

**È falso.** Il corso, video 47:

> *"Un'altra cosa da non fare mai, e ripeto mai, è spostare lo stop loss
> **in difetto** dopo aver aperto l'operazione"*

Vieta di **abbassare** lo stop, non di alzarlo. E il trailing implementato
alzava soltanto: *"lo stop non scende MAI"* era la sua proprietà
principale, coperta da test apposta.

Non solo: il corso, sempre video 47, dice cosa fare se si lascia correre
la posizione oltre 3R —

> *"ricordati comunque di uscire dall'operazione se ci sono chiari segnali
> di inversione. Esempio, un Bowai contrario... oppure **chiusure sotto
> medie mobili importanti come la 200 periodi, la 100 periodi**"*

Quindi l'uscita del runner sulla SMA200 è del corso (confermata), ma il
corso **non vieta** di proteggere il guadagno alzando lo stop.

**La prima motivazione resta valida**: fuori campione il trailing vince
solo in 8 anni su 16. Quella misura non cambia. Ma la decisione era stata
presentata all'utente come "due ragioni", e **una delle due non esisteva**.

---

## Verificato e CORRETTO

| | Affermazione | Fonte |
|---|---|---|
| A1 | Rischio 1% per operazione (1-2% il tetto) | video 45 ✅ |
| A3 | A +1R: vendi metà e porti lo stop a pareggio | video 47 ✅ *"venderai metà titoli e porterai lo stop loss a pareggio"* |
| A4 | A +3R/4R si chiude | video 47 ✅ — ma dice *"chiudere **l'intera posizione** o gran parte"*, più aggressivo del 30% del bot |
| A6 | Il residuo esce sotto la media a 200 (o 100) | video 47 ✅ |
| A8 | Lo stop va messo sempre, subito | video 47 ✅ *"non si apre mai un'operazione senza stop loss"* |
| B1 | Sei criteri di trend | video 34 ✅ *"sono sempre sei punti"* |
| B4 | ADX sopra 30 e crescente | video 34 ✅ |
| D1 | Volume minimo ~100.000 scambi al giorno | ✅ *"focalizzati intorno ad almeno i 100.000 volumi medi giornalieri"* |
| D3 | Il corso insegna anche gli short | ✅ una lezione intera |

## Verificato e SBAGLIATO

| | Cosa era stato scritto | Cosa dice il corso |
|---|---|---|
| A5 | *"Lo stop resta fermo, non sale"* | **Falso.** Vieta solo di **abbassarlo** |
| A2 | *"Massimo 12 posizioni (12%)"* | L'esempio del corso è **10 operazioni = 10%**. Il 12 non compare |

## Ancora da verificare

I 7 pattern e i loro dettagli, le soglie di volatilità, i filtri sul
prezzo, l'allineamento col settore, il PAC, e le regole degli ETF. La
parola "sette pattern" non compare come tale: i pattern vanno contati
leggendo i video 29-41 uno per uno.

---

## Cosa cambia adesso

1. **Riproporre all'utente la scelta 1% / 0,5%** con la citazione del
   corso, che dice 0,5% per chi inizia. È la decisione più importante.
2. **Correggere la motivazione del trailing** ovunque sia scritta:
   STRATEGY.md dice "modifica contro il corso" e non è vero.
3. **Verificare il tetto aggregato**: il bot usa 12%, l'esempio del corso
   è 10%.
4. Completare la lettura dei video su pattern e filtri.
