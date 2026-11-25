# OneCiak: contesto per Claude

Letto a ogni sessione (le sessioni non condividono memoria). Solo come stanno
le cose oggi e dove trovare il resto; la storia sta in git.

## Il progetto

OneCiak (oneciak.com) dà a filmmaker indipendenti (registi al primo film,
sceneggiatori, produttori indipendenti, neolaureati) un'analisi di mercato
del loro progetto: anteprima gratis subito, report completo gratis via
email. Prendono decisioni vere di tempo e soldi: deve essere credibile e
utile davvero. Antonio: "una piattaforma che ti aiuta a realizzare un
progetto, non chiacchiere".

**Spiegato semplice** (versione approvata): chi ha un'idea per un film,
lungo o corto, scrive di cosa parla, quanto costa e a che punto è. Il report
risponde a tre domande: 1) Il mio film sta in piedi? (voto su storia, soldi,
pubblico, festival, distribuzione, e per ognuna cosa non va e cosa fare);
2) Cosa faccio adesso? (una sola azione per questa settimana); 3) A chi mi
rivolgo? (nomi veri: produttori con l'email già pronta, fondi con chi può
fare domanda, festival con le scadenze nel calendario). Ogni nome viene da
una pagina trovata e controllata; date, cifre e citazioni restano solo se
sono scritte lì. Senza fonte la voce non compare.

Founder: **Antonio Brasile** (ragazzo). Scrive in italiano, informale, con
typo quando è frustrato: non vuol dire che vuole un tono più formale.

- Repo `antoniobr97-a11y/oneciak`, branch di lavoro
  `claude/website-completion-aesthetics-6wknns`, base `main`.
- `index.html` è tutta l'app (CSS, poi HTML, poi JS). Backend: Netlify
  Functions in `netlify/functions/`. Deploy automatico su push a `main`.

## Regole di Antonio (non derogabili)

0. **Come parlargli**: sempre in italiano, parole semplici, risposte corte.
   In inglese solo i testi del sito.
1. **Verificato alla fonte** ("fonti verificate e mai cazzate"): comando,
   pagina ufficiale aperta, misura sui pixel, e dire da dove viene. Uno
   strumento misura solo quello che misura (WebSearch non è Google, Chromium
   non è Safari, locale non è live): se non posso verificare, dirlo. Persone
   o studi da consigliare: solo da registri ufficiali, ed esistere non vuol
   dire essere bravi. Se sbaglio, dirlo subito e correggere.
2. **Ogni contenuto promozionale lo vede prima lui** (post, Product Hunt,
   Reddit, email a scuole): testo esatto e anteprima, poi il suo ok. Né
   Claude né l'agente del lunedì postano o inviano.
3. **Virgole e punti al posto dei trattini lunghi**, nei messaggi e nel
   prodotto (`noDash()` li toglie dal testo dell'AI; `tests/lint.js` dal
   codice).
4. **Dimostrare le modifiche**: foto prima/dopo, misure, numeri.
5. **Su main solo quando scrive "pubblica"**: prima si prepara sul branch, si
   prova, si mostrano foto e numeri. "Vai" o "procedi" vogliono dire prepara
   e prova. **Controllo del lunedì**: gli errori li corregge e li prova da
   solo, poi gli scrive cosa ha fatto; online quando Antonio scrive
   "pubblica". Errori: cose rotte (errori nella pagina, menu, PDF, modulo,
   pagina più larga dello schermo, testo azzurro), link morti, falle della
   sicurezza da fuori, fatti scaduti o cambiati sulla fonte. Da chiedere
   prima: aspetto o testi del sito, cose nuove, motore e prompt, privacy e
   termini, post e messaggi promozionali, spese.
6. Domande esplorative: risposta breve con una raccomandazione.
7. **Onestà**: numeri per gli utenti solo veri; link sempre verificati
   (`_util/linkCheck.js` per i report).
8. **Sito da designer vero**: testo a sinistra, card diverse tra loro,
   bottoni con angoli da 10px, etichette come parole in grassetto accanto ai
   contenuti (mai sopra i titoli).
9. **Sempre pulito**: quando qualcosa cambia o si toglie, nello stesso commit
   va via quello che resta indietro (codice non chiamato, CSS senza
   elementi, file non usati, commenti e voci superate dei file di contesto).
10. **"Tutto controllato" non esiste**: dire cosa è stato controllato e cosa
    no. Una cosa che deve essere "come" un'altra si misura accanto all'altra.

## Controllare e pubblicare

- **Controlli**: `tests/check.sh` lancia tutto su un server locale (regole
  nel codice, sintassi, 160 prove di funzioni, 240 viste, regole di design,
  pressione dei tasti, movimenti rispetto al sito vero, foto prima e dopo
  da guardare con gli occhi). `tests/check.sh --quick`: solo il codice, in
  pochi secondi. Dopo ogni modifica, prima di dire che è fatta.
- **Pubblicare**: `tests/publish.sh "messaggio" file...` dal branch di
  lavoro, solo dopo "pubblica": rifà i controlli, pubblica solo se passano,
  aspetta che oneciak.com serva i file nuovi byte per byte e riprova le
  funzioni sul sito vero. Mai merge di PR (un merge via API è risultato
  vuoto).
- Netlify ha un limite al mese: raggruppare le modifiche, mai pubblicare
  solo note o CLAUDE.md, la preview #81 solo per il motore.
- Safari vero non c'è (macchina Linux): per Safari serve l'iPhone di
  Antonio. Cosa resta a mano: `docs/controlli.md`.

## Design, in breve

Chiaro e scuro seguono il dispositivo; titoli **Geist**, il resto
**Carlito** (font in `/fonts`, niente Google Fonts). Una sola scala di
caratteri (24, 18, 15, 14, 13; 16 per menu e roadmap), un solo segno per le
liste, voti "X.X/10" nel colore del testo con il colore solo sulla barretta,
una sola pressione dei tasti (0.97 bottoni, 0.99 righe, 160 ms `--ease`),
icone disegnate. Le regole che una macchina legge stanno in `tests/lint.js`
e `tests/rules.js`. Tutti i dettagli (colori, movimento, pagine, flusso,
report di esempio, roadmap): **`docs/sito.md`**, da leggere prima di toccare
aspetto, testi o comportamento del sito.

**Bocciato da Antonio, da non riproporre**: fasce grigio-azzurre/rosa da
vetro smerigliato; "ora d'oro"; luce parassita da destra; macchia
rossa/ambra in alto a destra; altre varianti di satinato/grana; palette
"intensa" e "Warm Neutrals"; sito vestito da carte di produzione, ciak, foto
d'archivio, logo gigante nel footer; più di 5 aree; il PDF di una pagina; il
pulsante "Next" tra le aree; contatti sparsi dentro le aree; scritte rosse
sotto le caselle; le guide; roadmap o guide in fondo alla home; un riquadro
glossario; colori diversi per pallini e voti; serie TV; documentari;
etichette "Tier A/B/C" sui festival; cronometro dell'attesa in una pillola;
un caricamento che finge di avanzare; gergo da marketing ("market intelligence",
"leverage").

## Dove trovare il resto

- **`docs/motore.md`**: il motore dei report (modello, costi, controlli
  sulle fonti, idoneità, scrittura, voti, qualità misurata, preview #81). Da
  leggere prima di toccare `netlify/functions/` o di giudicare un report.
- **`docs/progetto.md`**: ricerca sui filmmaker, sicurezza, questioni
  legali, controllo del lunedì e marketing, strumenti e skill installate.
- **`docs/controlli.md`**: cosa prova ogni programma in `tests/` e i
  controlli a mano (link esterni, sicurezza da fuori, analisi vera).

## Legale (in sospeso: Antonio sente un avvocato)

Il nome di Antonio non va sul sito finché non decide. Antonio non ha
partita IVA. Privacy incompleta rispetto al GDPR art. 13; dettagli e
proposte (strada A o B) in `docs/progetto.md`.

## Cosa manca, in ordine

1. Avvocato: privacy, strada A o B, nome di Antonio; poi riscrivere privacy
   e termini.
2. Prima del lancio: tetto di spesa Anthropic e ricarica del credito.
3. Prova con 5 filmmaker che Antonio conosce (piano e messaggi pronti il 18
   novembre 2026): conta solo un passo concreto che viene dal report,
   chiesto con il dettaglio (a chi, cosa). Poi 20-30 filmmaker veri (per
   esempio una scuola di cinema). Ricontattarli richiede il loro consenso.
4. Lancio (Product Hunt, Reddit, scuole) dopo avvocato e prova; ogni testo
   lo approva Antonio.
