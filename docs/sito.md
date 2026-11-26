# OneCiak: il sito nel dettaglio

<!-- Letto solo quando serve: il puntatore sta in CLAUDE.md. -->
Come è fatto il sito oggi: design, pagine, flusso, report di esempio. Le
decisioni sono di Antonio; tra virgolette il motivo, perché non vengano
riproposte. La storia sta in git.

## Design

- **Solo bianco e nero** ("non voglio assolutamente più colori", 26
  novembre 2026): ogni colore è un grigio esatto (R=G=B), anche in roadmap,
  privacy, termini, 404, PDF, mail e immagini; `tests/lint.js` blocca i
  colori nel codice, `check.sh` i pixel colorati nelle immagini.
  `og-image.png` (anteprima dei link) rifatta in bianco e nero;
  `email-header.jpg` è nero pieno e resta solo per le mail già inviate. Niente
  bagliori né accenti. `--danger` e `--success` valgono come il testo:
  errori e conferme si capiscono dalle parole. Etichette in grassetto nel
  colore del testo; barre dei voti, linea dell'indice e dei passi del
  modulo in `currentColor`.
- **Chiaro e scuro seguono il dispositivo** (`prefers-color-scheme`), niente
  pulsante; blocchi "LIGHT AND DARK" in fondo a index.html e
  `roadmap/roadmap.css`. Scuro: `--night:#0f0f0f`, testo `#eeeeee`, grana
  leggera. Chiaro: bianco, testo `#161616`, testo piccolo `#3a3a3a`. Senza
  preferenza: hero nero che sfuma (`in oklab`) verso `--paper:#f1f1f1`.
- **Font** in `/fonts` (niente Google Fonts, CSP `font-src 'self'`): titoli
  Geist, il resto Carlito (`size-adjust: 112%`). PDF: `carlito-*-pdf.ttf`,
  `geist-700-pdf.ttf`, `geist-300-pdf.ttf` (pacchetto `geist` 1.9.2, OFL).
  Mail: Calibri, Carlito, Arial; titolo in Geist dove il programma lo
  carica. Raptor Text è a pagamento: solo con licenza.
- **Una scala di caratteri** in tutto il sito ("troppi titoli grandi, troppe
  robe piccole"): 24 titoli di sezione e voti delle aree; 18 titoli delle
  righe e logline; 15 testo; 14 etichette e sottotitoli; 13 fonti, note,
  piè di pagina; 16 per domande del menu e testo della roadmap. Fuori scala
  solo titolo del film, voto e logo. Mail: 13-18 più titolo e voto. PDF
  (punti): 48 titolo, 14 logline, 13 titoli, 11 riassunto, 10 testo, 9
  note.
- **Bottoni**: angoli 10px, testo a sinistra nella pagina. I principali
  hanno tutti la misura del bottone della home, 240x51, testo 15px ("fai
  grandi tutti i bottoni uguali"): Analyze your project, menu, Analyze my
  project, Email me the full report, Analyze another project, Send, Try
  again, Send me a sign-in link; una regola sola (`:is(...)` vicino a
  `.row-panel`), prova in `functions.js`.
- **Etichette** come parole in grassetto accanto al contenuto, mai sopra i
  titoli; niente numeri decorativi né maiuscolo spaziato. Icone disegnate
  (SVG `.ic` 12px, ~6px dalla parola), mai simboli di testo.
- **Un segno, un voto**: stesso pallino grigio in tutte le liste; voti
  "X.X/10" nel colore del testo; barre della scheda in home uguali a quelle
  del report (prova in `functions.js`).
- **Movimento** (`.claude/skills/emil-design-eng`): `--ease:
  cubic-bezier(0.23, 1, 0.32, 1)` ovunque; aperture 220 ms (`openIn`);
  niente `transition: all` né `scale(0)`. Una sola pressione ("la stessa
  animazione quando clicchi i tasti", blocco "ONE PRESS"): bottoni e icone
  `scale(0.97)`, righe e schede `scale(0.99)`, 160 ms; prova in
  `tests/press.js`. Con "Riduci movimento" animazioni e transizioni sono
  `none` (con 0,01 ms il titolo del report si misurava a metà). Un
  cliccabile con animazione d'entrata usa `backwards`, non `both` (`both`
  bloccava il tocco). Hover solo dentro `@media (hover: hover) and
  (pointer: fine)`; ogni cliccabile ha `:active`; su touch aree ~44px.
- **Mai `inherit` per il colore dentro un `<button>`**: su iPhone Safari i
  bottoni sono azzurri (prova: `:where(button){color:rgb(0,122,255)}`).
- **Schermi stretti**: con il testo di Safari ingrandito un telefono è
  largo ~260px; `min-width: 0` su griglie e flex; nessuna pagina più larga
  dello schermo da 240 a 1600px.
- **Contrasto** misurato sui pixel: 4.5:1 testo piccolo, 3:1 titoli grandi.
- Niente banner cookie (nessun cookie né tracker; localStorage solo per il
  login My Reports). La casella del disclaimer sulla home resta
  (`termsCheck`).

## Pagine e flusso

- **Home**: titolo della pagina il più grande (40-86px); scheda con i voti
  veri di Northbound fatta come l'apertura del report (titolo 28-40px, voto
  32px, nessuna frase sotto il voto). Navbar trasparente, poi vetro, poi
  chiara (`updateLandingNav()`). Menu: "How it works" in una frase, domande
  frequenti che si aprono come le righe del report; in fondo e nel menu
  solo Privacy Policy e Terms of Service. Piè di pagina `.l-foot`.
- **Modulo**: sezioni separate da una linea, niente card. Solo
  lungometraggi e cortometraggi di finzione. "Where you are": fase
  (obbligatoria), chi produce, durata, già mostrato. Campi a 16px su touch,
  alti quanto il testo di esempio (`fitPlaceholders`). Campi obbligatori
  vuoti (`REQUIRED`, 7): solo un bordo (`markMissing`), la pagina sale al
  primo vuoto, sotto il bottone "N fields are missing, marked above.".
  Paese e lingua con la maiuscola (`properName`, uguale in
  `_util/project.js`). Cursore del budget 14px piatto.
- **Caricamento**: titolo su una riga (`setLoadingTitle`, da 40 a 24px;
  sul telefono un nome lungo va a capo), una frase, una linea sottile con
  un tratto che la attraversa (`.loading-line`): dice "sto lavorando", mai
  una percentuale, perché il progresso vero non si conosce. Nel report
  completo, sotto, una frase sola sui tempi.
- **Apertura del report** ("come A24"): nome del film grande come un
  manifesto (`fitTitle`, 24-168px), crediti, logline (`setHeroTitle`),
  scheda col voto (32px) e "Average of the five areas", riassunto 15px
  grigio. Logline e riassunto larghi quanto titolo e scheda. Stessa apertura
  nel PDF (copertina) e nella mail.
- **Aprire e chiudere** (aree, righe di "Your path", blocchi): una aperta
  per gruppo; il titolo toccato resta fermo, poi la pagina scivola finché è
  12px sotto le barre (`settleOpened`, `scrollUnderBars` con `offsetTop`:
  un'area non ancora comparsa sta 28px più in basso; sul telefono conta la
  direzione, perché salendo torna l'intestazione). Le righe `<details>` le
  apre il browser (con `preventDefault` su iPhone non si aprivano).
- **Report completo**: riassunto (`executive_summary`; 4 righe e "Read
  more" su telefono); "Your film, area by area" (5 aree chiuse,
  `toggleAccordion`); "Your path" (`buildPath`), scaletta di righe chiuse
  con i primi nomi visibili (`namesLine`): This week, Make a short first
  (solo lungometraggio e "First film"), Find a producer (non c'è se il
  produttore c'è già), Find the money (non c'è da "Funded" in poi), Get
  seen, Find who sells it. "Una scaletta già presentata da noi, non mille
  bottoni e mille link": niente calendario, niente riga verso la roadmap.
  In fondo, due per riga, PDF e "Report a problem" (solo nei report veri,
  apre il modulo di segnalazione); sotto "Analyze another project". Solo
  nel PDF: piano a fasi, marketing, budget, legale, piano a 90 giorni.
- **"For later"**: per un film non ancora girato, Festival e Distribuzione
  si aprono con "For later: ..." (`laterNote`).
- **Anteprima**: titolo, voto, riassunto, 5 aree, poi "Biggest risk.",
  "Biggest opportunity." e "Your next step." in grassetto accanto al testo
  (15px), richiesta del report completo in una frase, PDF e "Analyze
  another project".
- **Piè di pagina del report** (`.r-foot` con dentro `.l-foot`): fuori
  dalla colonna, largo quanto indice e report; frase legale in piccolo
  (solo nel report completo: nell'anteprima la dice già la casella), poi
  OneCiak, Privacy, Terms. Su computer l'indice sale con la pagina e si
  ferma 40px sopra (`place()`).
- **Indice** (`mountReportNav`, `REPORT_PARTS`): "Does my film stand up?"
  con le 5 aree e il voto, poi "Your path" coi passi (`goToStep`). Dai
  1100px colonna a sinistra, sempre presente ("farli comparire tutto a un
  tratto non mi piace"): parte all'altezza di "Your film, area by area",
  sale con la pagina e si ferma sotto l'intestazione. Righe identiche ai
  passi del modulo ("la stessa identica cosa"): quella attuale scivola di
  12px e prende la linea in 0.3s. Su portatili bassi le righe si stringono
  (prova a 1366x657, 1280x600, 1440x700). Sotto i 1100px barra con la
  sezione attuale e "Sections"; l'elenco si apre dentro la barra (fuori,
  iPhone Safari può non ricevere i tocchi). Nell'anteprima solo le aree.
- **Glossario sulla parola** (`glossify`, `GLOSSARY`): prima volta di ogni
  termine sottolineata a puntini, il tocco apre una nuvoletta; tocco fuori
  o Esc la chiude. Mai in link, bottoni, titoli, fonti, email.
- **"More" solo sopra le 90 parole** (`FOLD_WORDS`).
- **Report di esempio Northbound**: report vero del motore (voto 5.0), fonti
  controllate il 23 ottobre e il 2 novembre 2026; produttori Vivo Film,
  Leone Film Group, Lava Films verificati a mano; TorinoFilmLab FeatureLab
  2027 "Closed (5 November 2026)".
- **`/roadmap/`**: 9 fasi, 49 lavori con spunta (`oneciak-roadmap-v1` nel
  browser), 25 citazioni con fonte ricontrollate parola per parola il 23
  novembre 2026. Si raggiunge dal menu ("Where do I start after my
  report?"). Se cambia una regola citata, ricontrollare.
- `/guides/*` rimanda alla home (301 in `netlify.toml`).
- **Traduttore del browser** permesso; solo i nomi propri (`.entry-name`,
  `.rblock-names`) hanno `translate="no"`.
