# OneCiak: contesto per Claude

Letto a ogni sessione (le sessioni non condividono memoria). Qui c'è solo
come stanno le cose oggi; la storia sta nella cronologia git.

## Il progetto

OneCiak (oneciak.com) dà a filmmaker indipendenti (registi al primo film,
sceneggiatori, produttori indipendenti, neolaureati) un'analisi di mercato
del loro progetto: anteprima gratis subito, report completo gratis via
email. Prendono decisioni vere di tempo e soldi: deve essere credibile e
utile davvero. Antonio: "una piattaforma che ti aiuta a realizzare un
progetto, non chiacchiere".

**Spiegato semplice** (versione approvata, per Antonio e il punto del
lunedì): chi ha un'idea per un film, lungo o corto, scrive di cosa parla,
quanto costa e a che punto è. Il report risponde a tre domande: 1) Il mio
film sta in piedi? (voto su storia, soldi, pubblico, festival,
distribuzione, e per ognuna cosa non va e cosa fare); 2) Cosa faccio
adesso? (una sola azione per questa settimana); 3) A chi mi rivolgo? (nomi
veri: produttori con l'email già pronta, fondi con chi può fare domanda,
festival con le scadenze nel calendario). Ogni nome viene da una pagina
trovata e controllata, di preferenza ufficiale; date, cifre e citazioni
restano solo se sono scritte lì. Senza fonte la voce non compare.

Founder: **Antonio Brasile** (ragazzo). Scrive in italiano, informale, con
typo quando è frustrato: non vuol dire che vuole un tono più formale.

- Repo `antoniobr97-a11y/oneciak`, branch di lavoro
  `claude/website-completion-aesthetics-6wknns`, base `main`.
- `index.html` è tutta l'app (CSS, poi HTML, poi JS). Backend: Netlify
  Functions in `netlify/functions/`. Deploy automatico su push a `main`.

## Regole di Antonio (non derogabili)

0. **Come parlargli**: sempre in italiano, parole semplici, niente gergo,
   risposte corte. In inglese solo i testi del sito.
1. **Tutto verificato alla fonte** ("fonti verificate e mai cazzate";
   "basta a dirmi bugie"): verificare davvero (comando, pagina ufficiale
   aperta, misura sui pixel) e dire da dove viene. Mai dedurre da uno
   strumento che non misura quella cosa (WebSearch non è Google, Chromium
   non è Safari, locale non è live): se non posso verificare, dirlo. Niente
   numeri a memoria; fonti in disaccordo, dirlo. Persone o studi da
   consigliare: solo da registri ufficiali, ed esistere non vuol dire
   essere bravi. Se sbaglio, dirlo subito e correggere.
2. **Ogni contenuto promozionale lo vede prima lui** (post, Product Hunt,
   Reddit, email a scuole): testo esatto e anteprima, poi il suo ok. Né
   Claude né l'agente del lunedì postano o inviano.
3. **Mai trattini lunghi (—)** nei messaggi e nel prodotto: virgole o
   punti. `noDash()` li toglie anche dal testo dell'AI (sito, PDF, email).
4. **Dimostrare le modifiche**: foto prima/dopo, misure, numeri. "Non vedo
   differenze" vuol dire mostrarlo meglio.
5. **Niente si pubblica senza il suo ok**: si prepara sul branch, si prova,
   si mostrano foto e numeri; su main solo quando scrive "pubblica". "Vai"
   o "procedi" vogliono dire prepara e prova. **Controllo del lunedì**
   (Antonio, 23 novembre 2026): gli errori che trova li corregge e li
   prova da solo, senza chiedere, poi gli scrive cosa ha fatto con foto e
   numeri; per metterli online Antonio scrive "pubblica". Errori vuol dire:
   cose rotte (errori nella pagina, menu, PDF, modulo, pagina più larga
   dello schermo, testo azzurro), link morti, falle del controllo "Sicurezza da fuori", fatti scaduti o cambiati
   sulla fonte (date, cifre, citazioni, ricontrollati parola per parola).
   NON rientrano e restano da chiedere prima: cambi di aspetto o di testi
   del sito, cose nuove, il motore dei report e i prompt, privacy e
   termini, post e messaggi promozionali, spese.
6. Domande esplorative: risposta breve con una raccomandazione.
7. **Onestà**: mai inventare o gonfiare numeri per gli utenti. Link sempre
   verificati (`_util/linkCheck.js` per i report).
8. Sito da designer vero, non "da AI": niente tutto centrato, card
   identiche, bottoni a pillola, gradienti speculari, spinner generici,
   etichette sopra i titoli.
9. **Sempre pulito**: quando qualcosa cambia o si toglie, nello stesso
   commit si toglie quello che resta indietro (codice non chiamato, CSS
   senza elementi, file e font non usati, commenti superati, voci vecchie
   di questo file). Dopo una pulizia: confronto pixel per pixel e prove
   delle funzioni (vedi "Controlli").

## Pubblicare su main

Netlify ha un limite al mese (piano a pagamento fino a fine novembre 2026,
promemoria `trig_01SEEuAVNJc5mCnfkSTcDufc` il 27 novembre per tornare al
Free): ogni pubblicazione su main e ogni aggiornamento della preview #81
consuma. Quindi mai pubblicare solo CLAUDE.md o note, raggruppare le
modifiche approvate, provare tutto in locale, la preview solo per il motore
dei report, giri completi sul sito vero solo dopo una pubblicazione.

Mai merge di PR (un merge via API è risultato vuoto). Sempre:
```bash
git fetch origin main
git checkout -B main-fixN origin/main
git checkout <branch-di-lavoro> -- <file del sito>   # o cherry-pick
git diff origin/main --stat            # deve essere NON vuoto, altrimenti STOP
git push origin main-fixN:main
git checkout claude/website-completion-aesthetics-6wknns
```
Poi `mcp__github__get_commit`: deve avere righe aggiunte e tolte vere. Poi
ciclo su `curl https://oneciak.com/?x=$i` finché trova una stringa NUOVA del
codice (su una riga sola): la CDN può servire la versione vecchia con 200.

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
  termini; aperture 220 ms con `openIn`, freccia che gira, pressione
  `scale(0.99)`; bottoni 160 ms; niente `transition: all` né `scale(0)`.
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

**Bocciato da Antonio, NON riproporre**: fasce grigio-azzurre/rosa da vetro
smerigliato; "ora d'oro"; luce parassita da destra; macchia rossa/ambra in
alto a destra; altre varianti di satinato/grana; palette "intensa" e "Warm
Neutrals"; sito vestito da carte di produzione, ciak, foto d'archivio, logo
gigante nel footer; più di 5 aree; il PDF di una pagina; il pulsante "Next"
tra le aree; contatti sparsi dentro le aree; scritte rosse sotto le caselle;
le guide; roadmap o guide in fondo alla home; un riquadro glossario; colori
diversi per pallini e voti; serie TV; documentari; etichette "Tier A/B/C"
sui festival.

## Pagine e flusso

- **Home**: compatta. Navbar trasparente, poi vetro, poi chiara
  (`updateLandingNav()`). Scheda di vetro con i voti veri di Northbound,
  fatta come l'apertura del report: titolo Geist 700 (28-40px), sotto i
  crediti, voto 40px (prima titolo 26px e voto 56px: "piccolo qui, un
  bestione una volta aperto"). Il titolo della pagina resta il più grande
  (40-86px, 12,5vw: 49px su un iPhone contro 31 della scheda). Niente riga "No account needed". Nel menu
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
- **Caricamento**: 5 dimensioni che avanzano (`startLoadingDims` e simili).
- **Apertura del report** ("come A24"): nome del film senza virgolette,
  grande come un manifesto (`fitTitle`: una riga larga quanto l'apertura,
  24-168px; i titoli lunghi vanno a capo tra le parole in circa 3 righe),
  sotto i crediti (genere · formato · paese · lingua) e la logline
  (`setHeroTitle`), poi la scheda di vetro col voto (48px, 40px sul
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
  prossimo passo, richiesta del report completo.
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
  appaiono; misurato a 1100, 1280, 1600: 0 scarti su 30 colpi di rotella). L'area attuale
  scivola di 8px e si accende col segno arancio in 0.3s, come i passi del
  modulo. Sotto i 1100px, barra con la sezione attuale e "Sections" che
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

## Motore dei report

- Modello `claude-haiku-5-5` (anteprima effort `low`) con ricerca web:
  anteprima 2 ricerche; report completo sezioni A-G di `reportPrompts.js`
  (ricerche B 6, C 5, D 6, E 5, G 5), `FULL_MAX_TOKENS` 32000 (meno tronca
  il JSON). Costo misurato: anteprima ~0,025 $, report completo ~0,35-0,40 $
  (la ricerca web è circa tre quarti). Credito prepagato il 9 novembre
  2026: 22,02 $, poi sceso con le prove. Limite di spesa Anthropic: 50 al
  mese.
- `grounding.js`: una voce resta solo se la sua fonte è tra i risultati
  della ricerca; date e cifre solo se sono sulla pagina (quelle del
  progetto contano come verificate); niente cifre da aggregatori; scadenze
  passate "Closed (...)"; `rule_quote` solo se è sulla pagina parola per
  parola (i PDF non si leggono); `applicant` solo con la sua `rule_quote`.
- **Produttori**: restano solo se una pagina della ricerca nomina azienda
  (senza Srl/Ltd...) e film insieme (`checkNamed`, `findNamingPage` su al
  massimo 25 pagine); un "film" uguale al nome dell'azienda è scartato.
  L'email non nomina mai un'azienda ([COMPANY NAME]). Come accettano
  progetti (`checkApproach`): solo la loro frase parola per parola, dalla
  pagina `approach_url` sul sito dell'azienda (`ownSite`: l'indirizzo
  contiene una parola distintiva del nome), escluse pagine di distribuzione
  e frasi tagliate a "contact:". Sul sito: "How they take projects, word
  for word" col link, altrimenti "not found on their site. Ask before you
  send a script." (una volta sola se nessuna ce l'ha). In cima al passo la
  regola di Film4 ("we cannot consider unsolicited material", channel4.com,
  controllata l'11 novembre 2026).
- **Chi può fare domanda** (`eligibility.js`): fondi, festival e laboratori
  la cui frase (`rule_quote`, `eligibility`, `fit`) esclude il progetto
  vengono tolti, anche nell'anteprima: paese (`excludes`, tabella di ~50
  paesi), formato, durata, lungometraggi già fatti e, per "First film",
  lavori precedenti richiesti (`excludesWork`). Solo frasi che limitano chi
  entra, non prima visione, soldi o lingua; frasi con "not" non giudicate.
  62 frasi di prova tutte giuste (12 novembre 2026). Sul sito "Who can
  apply" solo con la frase della fonte.
- **Film di confronto** (`checkComp`): solo se la pagina dice il genere (e
  "short" per un corto); anno e budget solo se sulla pagina. **Agenti e
  piattaforme** (`checkListed`): solo se la pagina contiene il nome.
- **Scadenze** (`closingDateIn`): conta la data dopo "until", "deadline",
  "by", "entro". Anche laboratori e mercati: passata "Closed (...)",
  assente "Not published on the source, check before planning"; finiscono
  nel calendario. Aggregatori (`AGGREGATORS`): il nome resta, scadenze,
  cifre e citazioni no; un fondo trovato solo su un aggregatore viene tolto
  e con lui le righe di "Before you can apply" che lo nominano
  (`dropStepsForGoneFunds`, che toglie anche quelle dei fondi scartati da
  altri controlli). Un fondo va via anche se viene da un sito di notizie
  (`NEWS`: variety, screendaily, cineuropa...) o se il report stesso lo
  dice preso da un "third-party site" (`THIRD_PARTY`). Dopo `linkCheck`,
  `dropDeadSources` toglie intera ogni voce con il link della fonte morto
  (prima restava la riga "Source" col link rotto). Una `rule_quote` che
  comincia a metà elenco ("soit par...", "or by...", `FRAGMENT`) non regge
  "Who can apply" e sparisce (il CNC diceva "solo società" ma accetta anche
  il regista). xhbt.org (da dove arrivò un fondo di Milano proposto a
  un progetto del Kansas) blocca i programmi: non verificato se è un
  aggregatore, non è in lista.
- `verifiedFacts.js`, fatti controllati a mano (ricontrollare se cambia la
  legge): tax credit italiano 30% per produttori indipendenti, tetto 4 mln
  (D.I. MiC-MEF 6/7/2026 n. 281); bando MiC selettivi 2026 (d.d. 15/5/2026
  n. 1238): scrittura per autori persone fisiche, opere oltre 52 min, in
  italiano, no IA; sviluppo e produzione solo imprese indipendenti
  italiane Ateco 59.1 con un'opera negli ultimi 5 anni (salvo società
  nuove). `applySelective` sistema queste righe.
- **Scrittura** (`STYLE`, anche nell'anteprima; `LENGTH` nel `PREAMBLE`):
  un'idea per frase, ~20 parole, "you", termini spiegati, mai "I"/"we";
  ogni area 3-4 frasi, problemi e punti di forza 1-3, consigli 2-3, ogni
  punto in una sola area. `stageRules`; rubrica `SCORING` (in tutte le
  chiamate, anche dell'anteprima): il voto giudica il progetto, mai la fase
  (copione non scritto, soldi non trovati, film non girato non abbassano il
  voto), con esempi area per area e tutta la scala; negli esempi JSON dei
  prompt nessun numero (un "6" lì faceva finire tutto tra 4,5 e 6).
  `_util/scores.js`: voti in numeri 1-10 (`normalizeScores`) e voto finale =
  media delle 5 aree (`overallFromAreas`). Misurato il 16 novembre 2026 su 6
  progetti diversi (2 giri ciascuno): prima 3,6-5,6, dopo 2,0-6,5, stabile
  entro 0,2. Nessun confronto con altri report ("più alto del 28% di 18
  progetti": erano quasi tutte prove, tolto). Niente previsioni di incasso
  né prezzi E&O. Ogni voce:
  "Source: dominio · checked data".
- **Qualità** (23 novembre 2026, 5 report nuovi della preview: corto
  italiano, lungo USA, primo film francese, film britannico girato, film
  croato finanziato): 86 voci, 68 giuste sulla fonte, 4 sbagliate (2 link
  morti, 1 fondo da un sito di elenchi, 1 "Who can apply" sbagliato), 14
  non verificabili da qui; le 3 cause corrette il 24 novembre (vedi sopra),
  poi 2 report di prova senza nessuno dei 3 errori. Nei 7 report 5 fondi su
  19 venivano da siti non ufficiali (creativepathwayscanada.com, variety.com,
  dossierdeprod.fr due volte, les-aides.fr): aggiunti alle liste, ma una
  lista non sarà mai completa. Prima misura (11 novembre 2026, 3 report: corto italiano,
  lungometraggio francese, lungometraggio USA): 57 voci con fonte, 46
  giuste, 0 sbagliate, 11 non verificabili da qui. Ogni giro dà voci
  diverse; alcuni siti (Wix) a volte non mostrano i film: ricontrollare
  più volte. Problemi noti: idoneità non controllata su fase e società
  richiesta; a volte nessun produttore verificato; regole di prima visione
  a volte parafrasate male; nei corti spesso nessun film di confronto
  (voluto).
- **Prove**: PR bozza #81 (`test-sourced-reports`), anteprima
  `deploy-preview-81--oneciak.netlify.app`, genera i report sulla preview.
  Ha commit "TEST ONLY": MAI su main né mergiata. Per aggiornarla: checkout
  dei file del motore dal branch di lavoro sopra
  `origin/test-sourced-reports`. Mail di prova a `delivered+X@resend.dev`.

## Ricerca

- Doc privato "Come si fa davvero un film" (claude.ai/artifact/JrLNDdn3koDmXdo6Lv3MuH):
  solo il 25,3% degli esordienti fa un secondo film entro 5 anni (Stephen
  Follows, 19 agosto 2026); in Italia senza società di produzione niente
  fondi per sviluppo e produzione; "Your first film will probably be
  funded" (Follows, 28 ottobre 2026). Da qui "Before you can apply", "Make
  a short first", produttori e calendario.
- Ricerca dell'11 novembre 2026 (report nello scratchpad, non nel repo):
  l'ostacolo principale è il produttore; molti produttori non leggono
  progetti non richiesti; nessuno fa gratis quello che fa OneCiak
  (controllato con WebSearch, non con Google); nessun dato su quante email
  a freddo funzionano: va misurato con persone vere.

## Sicurezza

- `analyze.js` accetta solo `{project}`: i prompt si costruiscono sul server
  (`_util/freePrompts.js`). `sanitizeProject` tiene solo i campi noti.
- `start-full-report` firma id+email+progetto (`payloadSig.js`); massimo 5
  report al giorno per email, 3 ogni 3 ore per IP, anteprime 10 l'ora per
  IP. IP mai salvati in chiaro (HMAC). Errori 500 generici al client.
  `admin-stats.html` manda la chiave in `X-Admin-Key`.
- Netlify pubblica tutta la cartella (`publish = "."`): CLAUDE.md,
  funzioni, package*.json, `.claude/`, `.impeccable/` chiusi con 404 in
  `netlify.toml`. Ogni nuovo file non del sito alla radice va aggiunto lì.

## Legale (in sospeso: Antonio sente un avvocato)

Antonio NON ha partita IVA. Privacy incompleta rispetto al GDPR art. 13
(titolare, basi giuridiche, trasferimenti USA, conservazione, reclamo al
Garante). NON scrivere il nome di Antonio sul sito finché non decide. Oggi
si conservano senza scadenza report, email e l'indice My Reports; proposte:
cancellazione dopo 30 giorni e niente My Reports ("strada A") o report solo
a schermo ("strada B"). Da valutare: AI Act art. 50(2), D.Lgs. 70/2003
art. 7. Scheda per l'avvocato: claude.ai/artifact/Y776k28X7HyxzMxcQgNXDX.

## Marketing

- Google indicizza già il sito (confermato da Antonio).
- Controllo del lunedì (lunedì 8:52 ora italiana, in automatico; Antonio:
  "ogni lunedì controlla il sito a fondo", "se trova errori li deve
  sistemare senza chiedermi", "devo solo dirti io pubblica"): parte nella
  sessione di lavoro principale, che può correggere e pubblicare
  (`trig_01Hw3VgdAYog52NywzNU8RK9`; la vecchia routine
  `trig_01LhjUc5ZkrXiqCkiqh5hiKo` girava in sola lettura ed è spenta).
  Fa: controllo a fondo del sito vero ("Controlli" qui sotto, con foto),
  correzione e prova degli errori secondo la regola 5 (online quando
  Antonio scrive "pubblica"), "punto della situazione"
  (sito in breve, cosa è cambiato dal git log di main, 3 cose da "Cosa
  manca") e 3 post come Artifact privato (bozze: li pubblica Antonio).
  Se cambiano i controlli, aggiornare anche il suo testo.
- r/Screenwriting vieta contenuti AI, r/Filmmakers vieta i post solo-link.

## Cosa manca, in ordine

1. Avvocato: privacy, strada A o B, nome di Antonio; poi riscrivere privacy
   e termini.
2. Prima del lancio: tetto di spesa Anthropic e ricarica del credito.
3. Prima, prova con 5 filmmaker che Antonio conosce: piano e messaggi
   pronti il 18 novembre 2026 (rivisti col plugin EGM); conta solo un passo
   concreto che viene dal report, chiesto con il dettaglio (a chi, cosa).
   Poi prova con 20-30 filmmaker veri (per esempio una scuola di cinema):
   quanti chiedono il report completo, quanti lo aprono, chi dopo 7 e 14
   giorni ha fatto davvero il passo consigliato; chiedere "qual è l'ultima
   cosa che hai fatto per il tuo film?". Ricontattarli richiede il loro
   consenso.
4. Lancio (Product Hunt, Reddit, scuole) dopo avvocato e prova; ogni testo
   lo approva Antonio.

## Controlli (dopo ogni modifica visibile o pulizia)

Due programmi nel repo (`/tests/*` chiuso con 404 in `netlify.toml`), da
lanciare su un server locale o sul sito vero, sempre tutti e due:
`NODE_PATH=/opt/node22/lib/node_modules node tests/functions.js [url]`
(151 prove su telefono e computer: menu, modulo, ogni area, ogni blocco,
ogni passo, ogni voce dell'indice, glossario, copia email, PDF,
calendario, roadmap, 404) e `node tests/pages.js [url]` (180 viste: ogni
pagina × 6 larghezze × 3 schemi; errori, richieste fallite, pagina larga,
testo azzurro, trattini lunghi, mezzi pixel). Se cambia una funzione, si
aggiorna il programma nello stesso commit. Terzo programma, `tests/rules.js`:
le regole di design (caratteri, `:active`, angoli 10px, maiuscolo,
contrasto) su ogni vista.

- **Giro sul sito vero**: home, menu, modulo, report di esempio tutto
  aperto, My Reports, roadmap, privacy, termini, 404 × larghezze 262, 320,
  393, 430, 1280, 1600 × chiaro/scuro/senza preferenza. Cercare errori JS,
  richieste fallite, pagina più larga dello schermo, testo azzurro, trattini
  lunghi, testi affiancati non allineati.
- **Funzioni**: modulo vuoto (7 caselle rosse), glossario, scaletta che
  cambia col progetto (primo film, produttore presente, finanziato, corto),
  copia email, PDF, calendario nascosto senza date, menu "Sections" (ogni
  area da più punti, telefono e computer), un'analisi vera su
  `/.netlify/functions/analyze` (NON start-full-report).
- **Codice della pagina**: estrarre lo script di index.html e passarlo a
  `node --check` prima di ogni prova (un errore di sintassi spegne tutto il
  sito).
- **Pulizia**: confronto pixel per pixel col codice vecchio (`git archive
  HEAD` su un'altra porta), telefono e computer, 3 schemi: 0 differenze.
- **Link esterni** di report di esempio e roadmap: 2xx/3xx. Locarno ha un
  controllo anti-robot (403): va aperto a mano.
- **Sicurezza da fuori** (dalla skill `web-perimeter-owasp-2025-audit` del
  pacchetto ECC, letta e provata il 23 novembre 2026, non installata; solo
  letture, mai la prova sulla cache sul sito vero): 404 per `/.git/HEAD`,
  `/.git/config`, `/package.json`, `/package-lock.json`, `/.npmrc`, `/.env`,
  `/CLAUDE.md`, `/netlify.toml`, `/.claude/settings.json`,
  `/.impeccable/config.json`, `/netlify/functions/*.js`; intestazioni HSTS,
  CSP, X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy;
  http con 301 verso https; le funzioni con `Origin` estraneo rispondono
  solo `https://oneciak.com`; corpo sbagliato a `analyze` dà un errore corto.
  La libreria PDF (jsPDF 2.5.1 da cdnjs) ha il sigillo `integrity`: deve
  essere uguale a quello di `api.cdnjs.com/libraries/jspdf/2.5.1?fields=sri`
  e il PDF deve scaricarsi; se si cambia versione, cambiare anche il
  sigillo. `/admin-stats.html` risponde 200 apposta (serve la chiave).

## Strumenti

- **Impeccable** (`.claude/skills/impeccable`): scanner di anti-pattern in
  locale, hook in `.claude/settings.local.json`. Comando:
  `.claude/skills/impeccable/scripts/impeccable detect index.html`; falsi
  positivi spiegati in `.impeccable/config.json`.
- **Elephant-Goldfish Model** (plugin `egm@egm` 0.1.1, github.com/google/
  elephant-goldfish-model, Apache 2.0, "not an officially supported Google
  product"; attivo da `.claude/settings.json`, solo istruzioni in testo,
  niente comandi automatici): prima di un cambiamento grosso, il piano lo
  rileggono revisori senza memoria della conversazione (`/egm:egm-review-loop`
  con `comprehension` e `design_critic`). Provato il 18 novembre 2026 sul
  piano della prova con 5 filmmaker: 2 problemi bloccanti trovati e corretti.
- **Emil Kowalski design-eng** (`.claude/skills/emil-design-eng`, commit
  c8a7962, MIT): regole per animazioni e tocco.
- **Prove nel browser**: script Playwright a mano con
  `NODE_PATH=/opt/node22/lib/node_modules node script.js` (Chromium già
  installato). Safari non c'è (macchina Linux): per Safari vero serve
  l'iPhone di Antonio o un suo Mac collegato.
- Server locale: `nohup setsid python3 -m http.server 8143 --directory
  /home/user/oneciak > log 2>&1 < /dev/null & disown` (muore tra un
  messaggio e l'altro). Script e prove stanno nello scratchpad.
- Funzioni del server in locale: installare `@netlify/blobs` nello
  scratchpad e usare `NODE_PATH`.
- Scartati: Taste, awesome-claude-design, Context7, Graphify, 21st MCP,
  Agent Skills, Playwright CLI e Playwright MCP (mai usati). Strix
  rimandato (serve una chiave e un tetto di spesa decisi da Antonio).
