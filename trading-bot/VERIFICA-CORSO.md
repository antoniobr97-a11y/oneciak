# Cosa credo che dica il corso — da verificare

## Perché questo documento esiste

`STRATEGY.md` dichiara di essere "una sintesi originale, scritta da zero…
**non una trascrizione del corso**". È vero: il corso non è mai stato
consegnato a chi ha scritto il codice. Quel documento è stato ricostruito
da quello che l'utente ha raccontato nella prima sessione.

Quindi ogni frase di questo progetto che comincia con *"il corso dice…"*
è in realtà **"il mio riassunto dice…"**, e nessuno l'ha mai controllata
contro il materiale vero.

Non è un dettaglio accademico. Il 13 settembre il trailing stop è stato
spento anche con la motivazione "contraddice il corso". Se la riga qui
sotto sul pareggio fosse sbagliata, quella decisione poggiava sul nulla.

**Solo l'utente può chiudere questo buco: il corso ce l'ha lui.**

Istruzioni: leggi ogni riga, e segna ✅ se è giusta, ❌ se è sbagliata,
❓ se il corso non lo dice affatto. Le righe ❌ e ❓ sono quelle che
contano: indicano dove il bot sta seguendo un'invenzione.

---

## A. Le regole che contano di più
*(un errore qui cambia il comportamento del bot ogni singolo giorno)*

| # | Quello che credo dica il corso | ✅/❌/❓ |
|---|---|---|
| A1 | Si rischia **1%** del capitale per operazione (ammesso fino al 2%) | |
| A2 | Massimo **12 posizioni aperte** insieme (12 × 1% = 12% nel peggiore dei casi) | |
| A3 | A **+1R**: si vende il **50%** e si sposta lo stop **al prezzo d'ingresso** | |
| A4 | A **+3R**: si vende il **30%** della quantità iniziale | |
| A5 | Lo stop **resta fermo** al prezzo d'ingresso: **non** sale col prezzo | |
| A6 | Il **20% residuo** corre finché la chiusura non scende sotto la **SMA200** del titolo | |
| A7 | Si entra con un ordine **stop di acquisto** sopra il massimo del setup | |
| A8 | Lo stop di protezione va messo **subito**, insieme all'ingresso | |

## B. Quando un titolo è "in trend"

| # | Quello che credo dica il corso | ✅/❌/❓ |
|---|---|---|
| B1 | Ci sono **6 criteri** di qualificazione del trend | |
| B2 | Ne bastano **2-3 su 6** perché il titolo qualifichi | |
| B3 | Si guardano gli **ultimi 2-3 mesi** (60 giorni) | |
| B4 | L'indicatore di volatilità usa **10 periodi** | |

## C. I pattern d'ingresso

| # | Quello che credo dica il corso | ✅/❌/❓ |
|---|---|---|
| C1 | I pattern sono **7** | |
| C2 | Nel "Bowai" il minimo deve essere di **almeno 6 mesi** | |
| C3 | Nel "Bowai" il titolo deve invertire in **5 giorni o meno** | |
| C4 | Nel pullback i **minimi devono essere decrescenti** | |
| C5 | Per Pivot e Second Entry lo stop va **sotto il minimo del pullback** | |

## D. Quali titoli si guardano

| # | Quello che credo dica il corso | ✅/❌/❓ |
|---|---|---|
| D1 | Volume minimo **100.000 azioni al giorno** (video 18) | |
| D2 | Gli short si fanno preferibilmente su titoli **sopra 80-100 $** | |
| D3 | Il corso prevede **anche gli short**, non solo acquisti | |
| D4 | Il titolo deve essere allineato al suo **settore** e al **mercato** | |

## E. Gli ETF (lungo termine)

| # | Quello che credo dica il corso | ✅/❌/❓ |
|---|---|---|
| E1 | Portafoglio "Harry Browne": **4 ETF al 25%** ciascuno | |
| E2 | Si ribilancia **ogni 3 mesi** (o quando uno sfora) | |
| E3 | Portafoglio "Advanced": si controlla **una volta al mese** | |
| E4 | Advanced usa la media a **10 mesi** per decidere dentro/fuori | |
| E5 | Gli ETF andrebbero **in euro o hedged**, non in dollari | |

## F. Cose che il bot fa e che NON so se il corso dica

*Queste le ho decise io o le ho prese dalla ricerca. Se il corso dice
qualcosa di diverso, va cambiato il bot.*

| # | Cosa fa il bot | il corso cosa dice? |
|---|---|---|
| F1 | Non compra se l'indice S&P 500 è sotto la sua media a 200 giorni | |
| F2 | Massimo **3 posizioni per settore** | |
| F3 | Gli short sono **disattivati** (perdevano in ogni test) | |
| F4 | Fra più candidati, preferisce quelli **vicini al massimo dell'anno** | |
| F5 | Scarta i titoli con volatilità annua **sotto il 25%** | |
| F6 | Scarta i titoli **sotto i 10 $** | |
| F7 | Controvalore minimo scambiato: **5 milioni $ al giorno** | |
| F8 | Un ordine d'ingresso non eseguito si annulla dopo **20 giorni** | |

---

## Come mandarmi il corso

Qualunque di queste cose basta, anche parziale:
- le **trascrizioni** dei video (testo)
- i **PDF** o le slide
- i tuoi **appunti**
- anche solo l'**elenco dei titoli dei video**, per capire cosa copre

Più materiale arriva, più la verifica è vera. Con il testo completo si può
fare il confronto riga per riga che è stato chiesto; senza, restano queste
domande.
