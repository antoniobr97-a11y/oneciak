# OneCiak: il sito nel dettaglio

<!-- Letto solo quando serve: il puntatore sta in CLAUDE.md. -->
Design deciso da Antonio, pagine, flusso e report di esempio. CLAUDE.md tiene
solo le decisioni principali e la lista dei bocciati.

## Design (deciso da Antonio)


**Chiaro e scuro seguono il dispositivo** (`prefers-color-scheme`), niente
pulsante. Blocchi CSS "LIGHT AND DARK" in fondo a index.html e a
`roadmap/roadmap.css`; anche privacy, termini, 404.
- **Scuro**: nero prugna `--night:#140d10`. UNA luce fissa allo schermo
  (`body::before`): petrolio a sinistra, rosso in basso a destra, grana.
- **Chiaro**: bianco `#ffffff`, stessa composizione (petrolio `#407381` a
  bassa opacità, rosso morbido), niente grana. Testo grigio piccolo
  `#3a3a3a`, rosso errori `#8a2419`.
- **Senza preferenza**: hero scuro con bagliori ambra/arancio/rosso/vino e
  petrolio, sfumatura `in oklab` verso la carta `--paper:#f4f1ec`.
- **Font** in `/fonts` (niente Google Fonts, CSP `font-src 'self'`): titoli
  **Geist**, il resto **Carlito** (`size-adjust: 112%`). PDF:
  `carlito-*-pdf.ttf`, `geist-700-pdf.ttf`, `geist-300-pdf.ttf` (pacchetto
  ufficiale `geist` 1.9.2, licenza OFL), Helvetica di riserva. Mail:
  Calibri, Carlito, Arial; titolo in Geist solo dove il programma lo carica
  (Apple Mail). Raptor Text è a pagamento: non usarlo senza licenza.
- **Scala dei caratteri del report** ("troppi titoli grandi, troppe robe
  piccole"): oltre a titolo del film, voto grande e logo, solo 5 misure.
  24 titoli di sezione e voti delle aree; 18 titoli delle righe, logline,
  riassunto; 15 testo, elenchi, nomi, frase del voto; 14 etichette,
  sottotitoli, bottoni; 13 fonti, note, piè di pagina, paesi. Niente mezzi
  pixel. Dal 24 novembre 2026 la stessa scala vale in tutto il sito
  (home, modulo, menu, My Reports, roadmap, privacy, termini, 404; 16 per
  domande del menu e testo della roadmap): via 11, 12,5, 13,5, 14,5, 15,5,
  16,5, 17, 19, 21, 22 px. Mail: 13, 14, 15, 16, 18 più titolo e voto. PDF
  (punti): 48 titolo, 14 logline, 13 titoli, 11 riassunto e frase del voto,
  10 testo, 9 fonti e note.
- Bottoni `border-radius: 10px`; testo a sinistra; hover solo dentro
  `@media (hover: hover) and (pointer: fine)`; ogni cliccabile ha `:active`
  con `scale(...)`; su touch le aree piccole allargate a ~44px.
- Niente etichette sopra i titoli né numeri decorativi: le etichette sono
  parole in Carlito grassetto (anche in roadmap: via il maiuscolo spaziato,
  24 novembre 2026). Icone disegnate, mai simboli di testo: frecce e Back
  sono SVG `.ic` 12px, circa 6px dalla parola (prima erano ← → ✕).
- Un elemento cliccabile con un'animazione d'entrata usa `backwards`, non
  `both`: `both` teneva il transform e la scheda Northbound non reagiva né
  al tocco né al mouse.
- **Un solo segno, un solo stile di voto**: stesso pallino grigio in tutte
  le liste; voti sempre "X.X/10" nel colore del testo, colore solo sulla
  barretta (blocco CSS "ONE MARKER, ONE SCORE STYLE"); anche Strong, Moderate,
  Weak sotto i voti delle aree sono grigi. Le barre della scheda in home
  hanno gli stessi colori del report (`bar-high/mid/low` da `scoreColor`;
  prima erano a mano, arancio sul 6.5 e bianco sul 4.5: Antonio se n'è
  accorto, i controlli no; ora `tests/functions.js` lo prova).
- **Movimento** (regole di Emil Kowalski, `.claude/skills/emil-design-eng`):
  `--ease: cubic-bezier(0.23, 1, 0.32, 1)` anche in roadmap, privacy,
  termini; aperture 220 ms con `openIn`, freccia che gira; niente
  `transition: all` né `scale(0)`. Con "Riduci movimento" del sistema
  animazioni e transizioni sono tolte (`none`), non accorciate a 0,01 ms:
  così il titolo del report si misurava a metà e restava piccolo. **Una sola pressione** (blocco CSS "ONE
  PRESS", Antonio 24 novembre 2026: "che abbiano tutte la stessa animazione
  quando clicchi i tasti"): bottoni, link-bottone e icone `scale(0.97)`,
  righe e schede che si aprono `scale(0.99)`, tutto 160 ms `--ease`; prima
  6 scale diverse (0,92-nessuna), 4 durate, 3 curve. Le parole nel testo
  (glossario, citazioni) non si rimpiccioliscono. Prova: `tests/press.js`.
- **Colori mai `inherit` dentro un `<button>`** (su iPhone Safari i bottoni
  sono azzurri). Prova: `:where(button){color:rgb(0,122,255)}` e cercare
  testo azzurro.
- **Schermi stretti**: con il testo di Safari ingrandito il telefono è largo
  ~260px; griglie e flex con `min-width: 0`. Nessuna pagina più larga dello
  schermo da 240 a 1600px.
- Banner cookie NON serve (nessun cookie né tracker; localStorage solo per
  il login My Reports). Il disclaimer con casella sulla landing resta
  (`termsCheck`).
- **Contrasto** misurato sui pixel (nascondere il testo con
  `:is(#zz,html) *{color:transparent!important}`). Testo piccolo 4.5:1,
  titoli grandi 3:1. Impeccable sui gradienti dà falsi positivi.

La lista dei bocciati sta in CLAUDE.md (una sola copia).

## Pagine e flusso


- **Home**: compatta. Navbar trasparente, poi vetro, poi chiara
  (`updateLandingNav()`). Scheda di vetro con i voti veri di Northbound,
  fatta come l'apertura del report: titolo Geist 700 (28-40px), sotto i
  crediti, voto 40px (prima titolo 26px e voto 56px: "piccolo qui, un
  bestione una volta aperto"). Il titolo della pagina resta il più grande
  (40-86px, 12,5vw: 49px su un iPhone contro 31 della scheda). Niente riga "No account needed" né "No account required." accanto al bottone del modulo. Solo il voto, senza frase (sotto ci sono già le 5 aree). Nel menu
  "How it works" è una frase sola, non righe che sembrano link. In
  fondo e nel menu solo Privacy Policy e Terms of Service; nel menu domande
  frequenti che si aprono come le righe del report.
- **Modulo**: niente card, sezioni separate da una linea. Solo
  lungometraggi e cortometraggi di finzione. "Where you are": fase
  (obbligatoria), chi produce, durata, già mostrato. Campi a 16px su touch.
  Campi obbligatori vuoti (`REQUIRED`, 7): solo bordo rosso (`markMissing`),
  la pagina sale al primo vuoto senza cursore, sotto il bottone "N fields
  are missing, marked in red above.". Caselle alte quanto il testo di
  esempio (`fitPlaceholders`).
- **Caricamento** (anteprima e report completo): titolo, una frase, una
  linea sottile con un tratto che la attraversa (`.loading-line`, 1,6 s,
  `--ease`): dice "sto lavorando", mai una percentuale, perché il
  progresso vero non si conosce (una barra che si riempie fingerebbe). Prima
  un pallino "avanzava" a tempo ("sa di AI"), poi le 5 aree ferme
  ("sembra tutto fermo", Antonio 26 novembre 2026).
  Mentre si fa il report completo, sotto la linea una sola frase ("This
  usually takes two or three minutes..."): niente cronometro in una pillola
  con pallino che pulsa (Antonio: "sa di AI"). Cursore del budget 14px
  piatto, senza anello bianco né ombra (prima 22px, "troppo grosso").
- **Apertura del report** ("come A24"): nome del film senza virgolette,
  grande come un manifesto (`fitTitle`: una riga larga quanto l'apertura,
  24-168px; i titoli lunghi vanno a capo tra le parole in circa 3 righe),
  sotto i crediti (genere · formato · paese · lingua) e la logline
  (`setHeroTitle`), poi la scheda di vetro col voto e accanto "Average of the five areas" (prima la frase del modello di 3-5 parole, tolta perché "sa di AI"; stessa riga in anteprima, PDF e mail) (48px, 40px sul
  telefono: prima 64 e 52, "sproporzionato"). Stessa apertura nel PDF
  (copertina) e nella mail (titolo 30-96px, ridotto sotto i 520px). PDF e
  mail: titoli come parole in grassetto, niente rosso e verde, voti "X.X/10".
- **Aprire e chiudere** (aree, righe di "Your path", blocchi dentro
  un'area): una aperta per gruppo; il titolo toccato resta fermo mentre le
  altre si chiudono, poi la pagina scivola finché è 12px sotto le barre
  (`settleOpened`, `jumpBy` senza `behavior:'instant'` che i Safari vecchi
  non conoscono, `scrollUnderBars`: sul telefono conta la direzione in cui
  si muoverà la pagina, non dove sta il titolo, perché salendo torna
  l'intestazione; il 23 novembre 2026 un titolo appena sotto le barre
  restava coperto); chiudere non sposta nulla. Le righe
  (`<details>`) le apre il browser (niente `preventDefault`: su iPhone il
  tocco su una riga non si apriva); il codice ascolta `toggle` e poi chiude
  le altre. La sezione
  attuale nell'indice si legge dalla posizione vera a ogni scroll.
- **Report completo**: un solo riassunto (`executive_summary`; 4 righe e
  "Read more" su telefono); "Your film, area by area" (5 aree chiuse, una
  aperta alla volta, `toggleAccordion`); poi **"Your path"** (`buildPath`):
  una scaletta numerata di righe chiuse con i primi nomi già visibili
  (`namesLine`); chiusa, una riga mostra titolo e una riga grigia come
  un'area chiusa (i nomi, o la frase tagliata a 2 righe se non ci sono
  nomi; la frase intera quando si apre: sul telefono sembrava già aperta),
  e il titolo "Your path" ha lo stesso spazio di "Your film, area by area": This week, Make a short first (solo lungometraggio e
  "First film", con le fonti di Stephen Follows), Find a producer ("Before
  you can apply", produttori, email da copiare; non c'è se il produttore
  c'è già), Find the money (non c'è da "Funded" in poi), Get seen
  (festival, laboratori, mercati), Find who sells it; sotto, il link alla
  roadmap. In fondo PDF e calendario (.ics, nascosto senza date future).
  Solo nel PDF: piano a fasi, rischio/opportunità, marketing, budget,
  legale, piano a 90 giorni. Antonio: "una scaletta già presentata da noi,
  non mille bottoni e mille link".
- **"For later"**: per un film non ancora girato (fase prima di
  "Shooting"), le aree Festival e Distribuzione si aprono con "For later:
  your film is not shot yet, so this is the plan for when it is finished."
  (`laterNote`), nel report e nell'anteprima.
- **Anteprima**: titolo, voto, riassunto, 5 aree, rischio, opportunità,
  prossimo passo ("Your next step." in grassetto accanto al testo, 15px come
  il resto: prima 18px grassetto, "perché il font è più grande?"),
  richiesta del report completo (una frase sola), poi due bottoni uguali,
  "Download this preview" e "Analyze another project" (prima un testo che
  "non sembrava nemmeno un tasto", più una nota ripetuta sul report
  completo). Le frasi accanto alle caselle sono a peso normale.
- **Indice** (`mountReportNav`, `REPORT_PARTS`): "Does my film stand up?"
  con le 5 aree e il voto, poi "Your path" con i passi del report (presi
  dalle righe della pagina; `goToStep` apre la riga come un tocco; la barra
  del telefono mostra il nome del passo), su computer e telefono. Dai 1100px colonna fissa a
  sinistra (testo del corpo in colonna di 640px): non sta accanto al titolo
  (Antonio: la colonna da subito "ha rovinato il titolo") e non compare
  all'improvviso ("farli comparire tutto a un tratto non mi piace", 24
  novembre 2026): c'è sempre, parte all'altezza di "Your film, area by
  area", sale con la pagina e si ferma sotto l'intestazione (`place` in
  `mountReportNav`, con `offsetTop` perché le aree salgono di 28px quando
  appaiono; misurato a 1100, 1280, 1600: 0 scarti su 30 colpi di rotella). Le
  voci sono righe identiche ai passi del modulo (Antonio: "la stessa identica
  cosa"): linea tra le righe, quella attuale si accende, scivola di 12px e
  prende la linea arancio in 0.3s; `tests/functions.js` le confronta col
  modulo e controlla che lo scivolamento sia animato (il blocco ONE PRESS
  l'aveva tolto: per `#areaNav` la transizione resta 0.3s). Sugli schermi
  bassi da portatile (1366x657 nel browser) le righe si stringono fino a 6px
  di margine così la colonna entra intera senza barra di scorrimento (Antonio
  la vedeva sul suo portatile; provato solo su 800 e 900 di altezza); prova
  in `tests/functions.js` a 1366x657, 1280x600, 1440x700. Sotto i 1100px, barra con la sezione attuale e "Sections" che
  compare quando tutta l'apertura è uscita; l'elenco si apre DENTRO la
  barra, che si allunga (fuori da una barra col vetro sfocato iPhone Safari
  può non ricevere i tocchi: "Your path" non si toccava). Nell'anteprima solo le aree.
- **Glossario sulla parola** (`glossify`, `GLOSSARY`, `openGloss`): prima
  volta di ogni termine sottolineata a puntini, il tocco apre una nuvoletta
  dentro lo schermo; secondo tocco, tocco fuori o Esc la chiude. Mai in
  link, bottoni, titoli, fonti, email.
- **"More" solo sopra le 90 parole** (`FOLD_WORDS`, `foldShort`,
  `parasFold`).
- **Report di esempio Northbound**: report vero del motore (voto 5.0), fonti
  controllate il 23 ottobre e il 2 novembre 2026; 3 produttori verificati a
  mano (Vivo Film, Leone Film Group, Lava Films; sui loro siti nessuna
  frase su come accettano progetti); TorinoFilmLab FeatureLab 2027 "Closed
  (5 November 2026)", e nei testi "the 2027 call closed on 5 November 2026"
  (trovato dal controllo del lunedì: tre frasi lo davano ancora aperto).
- **`/roadmap/`**: 9 fasi, 49 lavori con spunta (`oneciak-roadmap-v1` nel
  browser); le 25 citazioni (riquadri con fonte) ricontrollate parola per
  parola sulle fonti il 23 novembre 2026 (anche i 4 PDF, con `pdftotext`):
  Stephen Follows aveva cambiato due numeri sulle sue pagine (quote dei
  festival $25-45 e $37-67, 13,038 festival studiati), aggiornati. Si
  raggiunge dal report (`STAGE_TO_ROADMAP`) e dalla domanda "Where do I start
  after my report?" del menu; il link nella barra della home su computer è
  stato tolto il 24 novembre 2026 (telefono e computer uguali). CSS `roadmap/roadmap.css`
  allineato al sito. Se cambia una regola citata, ricontrollare.
- `/guides/*` rimanda alla home (301 in `netlify.toml`).
- **Traduttore del browser** permesso; solo i nomi propri (`.entry-name`,
  `.rblock-names`) hanno `translate="no"`. Nessuna riga "In English".
