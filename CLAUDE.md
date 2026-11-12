# OneCiak: contesto per Claude

Letto a ogni nuova sessione. Le sessioni non condividono memoria: qui c'è
SOLO come stanno le cose oggi. La storia sta nella cronologia git.

## Il progetto

OneCiak (oneciak.com) dà a filmmaker indipendenti un'analisi di mercato del
loro progetto: anteprima gratuita veloce, poi report completo gratuito via
email. Target: registi al primo film, sceneggiatori, produttori indipendenti,
neolaureati. Prendono decisioni vere di tempo e soldi: deve essere credibile e
utile davvero, non "carino".

**Spiegato semplice** (versione approvata, da usare con Antonio e nel punto
del lunedì): chi ha un'idea per un film, lungo o corto, scrive su OneCiak di
cosa parla, quanto costa e a che punto è. Riceve subito un'anteprima gratis
e, lasciando l'email, il report completo, sempre gratis. Il report risponde a
tre domande: 1) Il mio film sta in piedi? (un voto su cinque cose: storia,
soldi, pubblico, festival, distribuzione, e per ognuna cosa non va e cosa
fare); 2) Cosa faccio adesso? (una sola azione per questa settimana e cosa
preparare prima); 3) A chi mi rivolgo? (nomi veri: produttori a cui scrivere
con l'email già pronta, fondi a cui chiedere soldi con chi può fare domanda,
festival con le scadenze da mettere nel calendario). Sul sito: le 5 aree,
poi una sola scaletta "Your path". Ogni nome viene da una pagina trovata
dalla ricerca e controllata, di preferenza quella ufficiale; date, cifre e
citazioni restano solo se sono scritte su quella pagina e non su un sito di
notizie o raccolte. Se la fonte non c'è, la voce non compare.

Founder: **Antonio Brasile** (ragazzo). Scrive in italiano, informale, spesso
con typo quando è frustrato: non vuol dire che vuole un tono più formale.

- Repo `antoniobr97-a11y/oneciak`, branch di lavoro
  `claude/website-completion-aesthetics-6wknns`, base `main`.
- `index.html` è tutta l'app (CSS in `<style>`, poi HTML, poi JS).
- Backend: Netlify Functions in `netlify/functions/`. Deploy automatico su
  push a `main`. Niente Figma: tutto fatto in codice.

## Regole di Antonio (non derogabili)

0. **Come parlargli**: sempre in italiano, anche i messaggi brevi e quelli di
   avanzamento; parole semplici, niente gergo tecnico; risposte corte. Restano
   in inglese solo i testi del sito, che è in inglese.
1. **Tutto verificato alla fonte** ("fonti verificate e mai cazzate,
   pensarci 100 volte"; "basta a dirmi bugie"). Prima di affermare un fatto
   verificarlo davvero (comando, pagina ufficiale aperta, misura sui pixel) e
   dire da dove viene. Mai dedurre da uno strumento che non misura quella cosa
   (WebSearch non è Google, Chromium non è Safari, locale non è live): se non
   posso verificare, dirlo. Niente numeri a memoria. Se due fonti non
   concordano, dirlo. Persone/studi da consigliare: solo se verificati su
   registri ufficiali, e dire che esistere non vuol dire essere bravi. Se
   sbaglio, dirlo subito e correggere.
2. **Ogni contenuto promozionale lo vede prima lui** (post, Product Hunt,
   Reddit, email a scuole/riviste): testo esatto e anteprima, poi il suo ok
   esplicito. Né Claude né l'agente del lunedì postano o inviano.
3. **Mai trattini lunghi (—)** nei testi che gli scrivo e nel prodotto: usare
   virgole o punti. `noDash()` li toglie anche dal testo scritto dall'AI (sito,
   PDF, email).
4. **Dimostrare le modifiche**: foto prima/dopo, misure sui pixel, numeri.
   "Non vedo differenze" vuol dire che devo mostrarlo meglio.
5. **Niente si pubblica senza il suo ok** (Antonio, 10 novembre 2026:
   "aspetta a pubblicare, ti do io l'ok"): si prepara sul branch, si prova in
   locale e sulla preview, si mostrano foto e numeri, e si pubblica su main
   solo quando scrive "pubblica". "Vai" o "procedi" vogliono dire prepara e
   prova, non pubblica.
6. Domande esplorative ("che altro si può fare?"): risposta breve con una
   raccomandazione, non elenchi infiniti.
7. **Onestà**: mai inventare o gonfiare numeri mostrati agli utenti. Link
   sempre verificati (`_util/linkCheck.js` per i report).
8. Vuole un sito da designer vero, non "da AI": niente tutto centrato, card
   identiche, bottoni a pillola, gradienti speculari, spinner generici,
   etichette sopra i titoli.
9. **Sempre pulito** (vale per ogni modifica, per sempre): quando qualcosa
   cambia o si toglie, nello stesso commit si toglie anche tutto quello che
   resta indietro: codice e funzioni non più chiamate, stili CSS senza
   elementi, file e font non usati, commenti che parlano di cose che non ci
   sono più, voci superate in questo file. Questo file descrive solo il
   presente, senza "prima era così". Dopo la pulizia: confronto pixel per
   pixel prima/dopo e prove delle funzioni (vedi "Controlli").

## Pubblicare su main (procedura obbligatoria)

**Netlify ha un limite al mese** (il 9 novembre 2026 Antonio era al 75%; il 10 novembre è passato al piano a pagamento e torna al Free a fine mese, promemoria `trig_01SEEuAVNJc5mCnfkSTcDufc` il 27 novembre):
ogni pubblicazione su main e ogni aggiornamento della preview #81 consuma.
Quindi: mai pubblicare solo CLAUDE.md o note (restano sul branch e partono
con la pubblicazione vera successiva); raggruppare le modifiche approvate in
una sola pubblicazione; provare tutto in locale prima; la preview solo per
provare il motore dei report; i giri di controllo completi sul sito vero solo
dopo una pubblicazione, non più volte di seguito.

Mai merge di PR (un merge via API è risultato vuoto e il sito è rimasto
vecchio). Sempre:
```bash
git fetch origin main
git checkout -B main-fixN origin/main
git cherry-pick <sha-sul-branch>       # o checkout dei file dal branch
git diff origin/main --stat            # deve essere NON vuoto, altrimenti STOP
git push origin main-fixN:main
git checkout claude/website-completion-aesthetics-6wknns
```
Poi `mcp__github__get_commit` sul commit: deve avere additions/deletions
reali. Poi ciclo su `curl https://oneciak.com/?x=$i` che cerca una stringa
NUOVA del codice (su UNA riga sola) finché la trova: la CDN può servire la
versione vecchia con status 200.

## Design (deciso da Antonio)

**Chiaro e scuro seguono il dispositivo** (`prefers-color-scheme`), niente
pulsante. Blocchi CSS "LIGHT AND DARK" in fondo agli stili di index.html e in
fondo a `roadmap/roadmap.css`; anche privacy, termini, 404.
- **Scuro**: nero prugna `--night:#140d10` ovunque. UNA sola luce fissa allo
  schermo (`body::before`): petrolio a sinistra + rosso in basso a destra, con
  grana.
- **Chiaro**: bianco vero `#ffffff`, stessa composizione dello scuro fissa
  allo schermo: petrolio luminoso `#407381` a bassa opacità a sinistra + rosso
  morbido in basso a destra. Niente grana. Testo grigio piccolo `#3a3a3a`,
  rosso errori `#8a2419`.
- **Senza preferenza**: hero scuro con bagliori ambra/arancio/rosso/vino e
  petrolio, sfumatura `in oklab` verso la carta `--paper:#f4f1ec`, satinato
  con grana nelle parti chiare.
- **Font** self-hosted in `/fonts` (niente Google Fonts, GDPR; CSP
  `font-src 'self'`): titoli **Geist**, tutto il resto **Carlito**
  (`size-adjust: 112%`). PDF: `fonts/carlito-*-pdf.ttf` caricati al clic,
  Helvetica di riserva. Mail: Calibri, Carlito, Arial. Raptor Text gli piaceva
  ma è a pagamento: non usarlo senza licenza.
- Bottoni `border-radius: 10px`; testo allineato a sinistra; colori
  ambientali asimmetrici; hover solo dentro `@media (hover: hover) and
  (pointer: fine)`; ogni cliccabile ha `:active` con `scale(...)`; su touch
  le aree cliccabili piccole sono allargate a ~44px senza cambiare l'aspetto.
- Niente etichette sopra i titoli né numeri decorativi. Le etichette sono
  parole in Carlito grassetto. Icone disegnate (freccia, spunta), mai simboli
  di testo come "+".
- **Un solo segno, un solo stile di voto**: tutte le liste del report hanno
  lo stesso pallino grigio; i voti sono sempre "X.X/10" nel colore del testo,
  il colore (debole/medio/forte) solo sulla barretta; titoletti tutti dello
  stesso colore (blocco CSS "ONE MARKER, ONE SCORE STYLE").
- **Movimento** (regole di Emil Kowalski, `.claude/skills/emil-design-eng`):
  curva `--ease: cubic-bezier(0.23, 1, 0.32, 1)` anche in roadmap, privacy e
  termini; aperture di aree, righe e domande del menu 220 ms con `openIn`,
  freccia che gira, pressione `scale(0.99)`; bottoni 160 ms; niente
  `transition: all` né `scale(0)`.
- **Colori mai `inherit` dentro un `<button>`**: su iPhone Safari i bottoni
  sono azzurri di base. Prova in Chromium: `:where(button){color:rgb(0,122,255)}`
  e cercare testo azzurro.
- **Schermi stretti**: con il testo di Safari ingrandito il telefono è largo
  ~260px; elementi di griglia e flex hanno `min-width: 0` e i testi lunghi
  vanno a capo. Nessuna pagina deve essere più larga dello schermo da 240 a
  1600px.
- Banner cookie: NON serve (nessun cookie né tracker, statistiche anonime
  self-hosted; localStorage solo per il login My Reports scelto dall'utente).
  Il disclaimer con casella sulla landing resta obbligatorio (`termsCheck`).
- **Contrasto**: misurarlo sui pixel veri (nascondere il testo con
  `:is(#zz,html) *{color:transparent!important}`: senza `:is(#zz,html)` le
  regole `!important` del sito vincono e il controllo dà falsi 1.0:1).
  Testo piccolo almeno 4.5:1, titoli grandi almeno 3:1. Impeccable sui
  gradienti dà falsi positivi.

**Bocciato da Antonio, NON riproporre**: fasce grigio-azzurre/rosa da vetro
smerigliato; "ora d'oro"; luce parassita da destra; macchia rossa/ambra in
alto a destra nelle intestazioni; altre varianti di satinato/grana; palette
"intensa" e "Warm Neutrals"; sito vestito da carte di produzione, ciak
nell'intestazione, foto d'archivio, logo gigante nel footer; più di 5 aree nel
report; il PDF di una pagina; il pulsante "Next" tra le aree; contatti sparsi
dentro le aree; scritte rosse sotto le caselle del modulo; le guide; la
roadmap o le guide nel fondo della home; un riquadro glossario; i colori
diversi per pallini e voti; le serie TV; i documentari; le etichette "Tier
A/B/C" sui festival (giudizio dell'AI senza fonte).

## Pagine e flusso

- **Home**: compatta, niente ripetizioni. Navbar trasparente, poi vetro, poi
  chiara (`updateLandingNav()`). Scheda del report di esempio in vetro con i
  voti veri di Northbound. In fondo solo Privacy Policy e Terms of Service
  (anche nel menu). Menu con domande frequenti che si aprono come le righe
  del report.
- **Modulo**: niente card, sezioni separate da una linea. "Where you are":
  fase (obbligatoria), chi produce, durata, già mostrato. Campi a 16px su
  touch (iOS non zooma). Campi obbligatori vuoti (`REQUIRED`, 7 campi): SOLO
  bordo rosso sulla casella (`markMissing`), anche quando è selezionata,
  nessuna scritta sotto, la pagina sale al primo vuoto senza mettere il
  cursore; sotto il bottone "N fields are missing, marked in red above.".
  Le caselle di testo sono alte quanto il loro testo di esempio
  (`fitPlaceholders`). Solo lungometraggi e cortometraggi di finzione: niente
  serie, niente documentari (Antonio, 10 novembre 2026).
- **Caricamento**: 5 dimensioni che avanzano invece di uno spinner
  (`startLoadingDims` / `finishLoadingDims` / `resetLoadingDims`).
- **Report completo**: titolo, voto nella scheda di vetro, un solo riassunto
  (`executive_summary`, 3-4 frasi; 4 righe + "Read more" su telefono; il PDF
  ha anche `overall_summary`); "Your film, area by area" (5 aree chiuse, una
  aperta alla volta, `toggleAccordion`; dentro giudizio, "What to do", "Red
  flags and strengths", Comparable films nel mercato); poi **"Your path"**
  (`buildPath`): una sola scaletta numerata di righe chiuse, ognuna con cosa
  fare in una riga e i nomi già visibili: This week (prossimo passo e cosa
  preparare), Make a short first (solo lungometraggio e "First film", con le
  fonti di Stephen Follows), Find a producer ("Before you can apply",
  produttori, email da copiare; non c'è se il produttore c'è già), Find the
  money (fondi; non c'è da "Funded" in poi), Get seen (festival, laboratori e
  mercati), Find who sells it (agenti di vendita); sotto, il link alla
  roadmap. In fondo "Download the full report" e calendario (.ics, nascosto
  senza date future). Solo nel PDF: piano a fasi, rischio/opportunità,
  marketing, budget, legale, piano a 90 giorni e i testi lunghi. Antonio:
  "una scaletta già presentata da noi, non mille bottoni e mille link".
- **Anteprima**: titolo, voto, riassunto, poi le 5 aree, poi rischio,
  opportunità e prossimo passo, poi la richiesta del report completo.
- **Indice del report** (`mountReportNav`, `REPORT_PARTS`): "Does my film
  stand up?" con sotto le 5 aree e il voto, poi "Your path". Dai 1100px in
  su è una colonna fissa a sinistra del testo (il testo si sposta a destra,
  colonna di 640px); sotto i 1100px è una barra sotto l'intestazione con la
  sezione attuale e il pulsante "Sections" che apre l'elenco. Compare quando
  titolo e voto in alto sono usciti dallo schermo. Nell'anteprima gratuita
  mostra solo le aree.
- **Glossario sulla parola**: `glossify()` sottolinea a puntini la prima
  volta di ogni termine di `GLOSSARY` in ogni parte del report. La parola è
  testo normale (si può selezionare), il tocco apre una nuvoletta vicino alla
  parola (`openGloss`, sotto se c'è spazio, sopra se no, sempre dentro lo
  schermo); un secondo tocco, un tocco fuori o Esc la chiude. Mai dentro
  link, bottoni, titoli, fonti, email, etichette che non vanno a capo.
- **"More" solo dove serve**: un testo fino a 90 parole (`FOLD_WORDS`) si
  vede intero; solo i più lunghi mostrano la prima frase e "More"/"Read
  more" (`foldShort`, `parasFold`).
- **Righe chiuse della scaletta**: sotto il titolo si vedono già i primi 3
  nomi (`namesLine`, al massimo 2 righe); il dettaglio si apre col tocco.
- **Report di esempio Northbound**: report vero del motore (voto 5.0), fonti
  controllate il 23 ottobre e il 2 novembre 2026; 3 produttori verificati a
  mano (Vivo Film, Leone Film Group, Lava Films); TorinoFilmLab FeatureLab
  2027 è segnato "Closed (5 November 2026)".
- **`/roadmap/`**: 9 fasi, 49 lavori con spunta (solo nel browser,
  `oneciak-roadmap-v1`), 27 citazioni verificate parola per parola il
  2026-10-24. Si raggiunge solo dal report (in fondo a "Your path",
  collegato alla fase del progetto con `STAGE_TO_ROADMAP`). CSS
  `roadmap/roadmap.css`, da tenere allineato al sito. Se cambia una regola
  citata, ricontrollare.
- `/guides/*` rimanda alla home (301 in `netlify.toml`).
- **Traduttore del browser**: permesso (Chrome, Safari traducono il sito).
  Solo i nomi propri (fondi, festival, aziende, film: `.entry-name`,
  `.rblock-names`) hanno `translate="no"`, così restano quelli da cercare.
  Nessuna riga "In English" sotto i nomi (Antonio: "i nomi non metterli").

## Motore dei report

- Modello `claude-haiku-5-5` (anteprima effort `low`), ricerca web Anthropic:
  anteprima 2 ricerche; report completo sezioni A-G di `reportPrompts.js`
  con ricerche B 6, C 5, D 6, E 5, G 5. `FULL_MAX_TOKENS` 32000 (con meno una
  sezione si interrompe a metà JSON). Costi misurati: anteprima ~0,025 $;
  report completo con produttori ~0,35-0,40 $ (misura del 9 novembre 2026:
  il credito è sceso da 22,46 a 22,02 $ con 1 report completo e 2 anteprime;
  la ricerca web è circa tre quarti della spesa). Credito prepagato rimasto
  il 9 novembre: 22,02 $ (circa 55 report completi). Limite di spesa
  Anthropic: 50 al mese (circa 120 report completi): da decidere con Antonio
  prima del lancio, insieme alla ricarica del credito.
- `grounding.js`: una voce (fondo, festival, film, agente, piattaforma,
  produttore) resta solo se la sua fonte è tra i risultati della ricerca;
  date e cifre solo se sono sulla pagina (i numeri del progetto, come budget
  e durata, contano come verificati); niente cifre da aggregatori;
  scadenze passate "Closed (...)" una volta sola; `rule_quote` resta solo se è
  sulla pagina parola per parola (i PDF non si leggono); `applicant` resta
  solo con la sua `rule_quote`. Produttori (`checkNamed`): restano solo se la
  pagina contiene il nome (senza Srl/Ltd/AB...) E il titolo del film; un
  "film" uguale al nome dell'azienda viene scartato. Funziona in ogni paese
  (provato: Svezia, Cina, Italia). L'email per i produttori non nomina mai
  un'azienda: usa [COMPANY NAME]. Se la pagina citata non nomina
  azienda e film insieme, il motore prova le altre pagine della stessa
  ricerca (`findNamingPage`, al massimo 25): quella che li nomina entrambi
  diventa la fonte. Come un produttore accetta progetti (`checkApproach`,
  dopo la scelta della fonte): si mostra solo la sua frase
  (`approach_quote`) parola per parola, dalla pagina `approach_url` trovata
  dalla ricerca e sul sito dell'azienda (l'indirizzo contiene una parola
  distintiva del nome, `ownSite`: niente festival, notizie, Wikipedia);
  scartate le frasi delle pagine di distribuzione (film finiti, non
  progetti) e quelle tagliate a "contact:" senza l'indirizzo.
  Sul sito, PDF e mail: "How they take projects, word for word" con il
  link alla pagina; senza frase "not found on their site. Ask before you
  send a script." (una volta sola in alto se nessuna azienda ce l'ha). In
  cima al passo la regola di Film4 ("we cannot consider unsolicited
  material", channel4.com, controllata l'11 novembre 2026). I 3 produttori
  di Northbound: sui loro siti nessuna frase (controllato l'11 novembre).
- Chi può fare domanda (`eligibility.js`): fondi, festival e laboratori la
  cui frase (`rule_quote`, `eligibility`, `fit`) esclude il paese del
  progetto ("non-French", "must not be residents or citizens of France",
  "must be residents of Italy") vengono tolti, anche nell'anteprima.
  Stesso controllo (`excludesWork`) su formato (corto o lungo), durata
  ("at least 60 minutes", "up to 30 minutes") e lungometraggi già fatti dal
  regista ("is for first and second features", "must have directed at
  least one feature"); con "First film" toglie anche le regole che chiedono
  lavori già fatti ("previous short film(s) ... must have been selected",
  La Résidence di Cannes): solo frasi che limitano chi entra, non quelle su
  prima visione, soldi o lingua; frasi con "not" non vengono giudicate. I
  paesi sono una tabella di circa 50. 62 frasi di prova (vere e difficili)
  il 12 novembre 2026, tutte giuste. Sul sito "Who can apply" compare solo con la frase
  della fonte; le righe dei passi "Find the money" e "Get seen" dicono di
  controllare la pagina ufficiale.
- Film di confronto (`checkComp`): restano solo se la loro pagina dice il
  genere del progetto (e "short" per un corto); pagine illeggibili o
  aggregatori non vengono giudicati. Anno e budget restano solo se sono
  sulla pagina.
- Agenti di vendita e piattaforme (`checkListed`): restano solo se la loro
  pagina contiene il nome (toglie descrizioni scambiate per nomi, come
  "French theatrical distributor backed by CNC release aid").
- Scadenza chiusa: conta la data dopo "until", "deadline", "by", "entro"
  e simili (`closingDateIn`), non la data più lontana della frase (La
  Résidence di Cannes: "open until September 30, 2026" per una sessione nel
  2027 risultava aperta).
- Laboratori e mercati hanno la scadenza come fondi e festival: passata
  diventa "Closed (...)", assente diventa "Not published on the source,
  check before planning"; finisce anche nel calendario .ics. Siti di notizie
  e raccolte (`AGGREGATORS`, compresi caligari.com.ar e filmcane.com): il
  nome resta, scadenze, cifre e citazioni no. Il prompt chiede di citare la
  pagina ufficiale e di lasciare fuori le chiamate con solo edizioni passate.
- `verifiedFacts.js`: fatti controllati A MANO, da ricontrollare quando cambia
  la legge. Tax credit italiano 30% per produttori indipendenti, tetto 4 mln
  (D.I. MiC-MEF 6/7/2026 n. 281). Bando MiC contributi selettivi 2026
  (d.d. 15/5/2026 n. 1238): scrittura = autori persone fisiche, opere oltre
  52 min, in italiano, no IA; sviluppo e produzione = solo imprese
  indipendenti italiane Ateco 59.1 con un'opera negli ultimi 5 anni (salvo
  società nuove). `applySelective` sistema queste righe (anche 'Split').
- Stile di scrittura (`STYLE` in `reportPrompts.js`, usato anche
  nell'anteprima): un'idea per frase, circa 20 parole al massimo, "you",
  verbi concreti, termini tecnici spiegati la prima volta, ogni punto detto una
  volta sola, mai "I"/"we" né racconti della ricerca. Lunghezza (`LENGTH` nel
  `PREAMBLE`): testo di ogni area 3-4 frasi, problemi e punti di forza da 1 a
  3, consigli 2 o 3, mai liste riempite; ogni punto appartiene a una sola
  area (le 5 aree si scrivono in chiamate separate). Antonio: "report
  leggero ma completo, non ripetitivo".
- Prompt: `stageRules` (fase del progetto), rubrica `SCORING` (voto = media
  delle 5 aree), niente previsioni di incasso in euro né prezzi E&O. Ogni
  voce: "Source: dominio · checked data" su sito, PDF e mail.
- Qualità misurata l'11 novembre 2026 su 3 report nuovi della preview col
  report accorciato (corto italiano, lungometraggio francese, lungometraggio
  USA, gli stessi delle misure precedenti): 57 voci con fonte, 46 giuste
  sulla fonte, 0 sbagliate, 11 non verificabili da qui (siti che bloccano i
  programmi). Lunghezza con tutto aperto: da 3.360-3.460 parole a
  2.570-2.840; testi delle 5 aree circa -40%. Misure precedenti: 54 voci,
  45 giuste, 2 sbagliate (10 novembre sera); 63 voci, 50 giuste, 1
  sbagliata (10 novembre). Ogni giro dà voci diverse: una sola corsa per
  progetto non misura l'effetto di una modifica. Alcuni siti (Wix, per
  esempio openfieldsproductions.com) a volte mostrano l'elenco dei film e a
  volte no: ricontrollare più volte prima di dire che un nome manca. Il controllo verifica nomi, film, date e
  citazioni sulla fonte, non la qualità dei consigli. Prima misura (22
  ottobre): report completi 78%. Problemi noti: l'idoneità si controlla su paese,
  formato, durata e lungometraggi già fatti, non su fase del progetto o
  società richiesta (restano al prompt e a "Before you can apply");
  a volte nessun produttore verificato (report francese); regole di prima visione a
  volte parafrasate male, fondi senza scadenza scritta, qualche film di
  confronto poco pertinente, a volte fonti da aggregatori, nei corti spesso
  nessun film di confronto (regola severa, voluto).
- **Prove**: PR bozza #81 (`test-sourced-reports`) = anteprima
  `deploy-preview-81--oneciak.netlify.app`, genera i report sulla preview.
  Ha commit "TEST ONLY" (mostra sempre il motivo dell'errore, limite 12;
  `CONTEXT` NON esiste mentre girano le funzioni): MAI su main, la PR non va
  mai mergiata. Per aggiornarla: checkout dei file dal branch di lavoro sopra
  `origin/test-sourced-reports`. Mail di prova a `delivered+X@resend.dev`.

## Ricerca "come si fa davvero un film"

Doc privato "Come si fa davvero un film: ricerca per OneCiak"
(claude.ai/artifact/JrLNDdn3koDmXdo6Lv3MuH). Punti chiave verificati: solo il
25,3% degli esordienti fa un secondo film entro 5 anni (Follows 2026); in
Italia senza società di produzione niente fondi per sviluppo e produzione. Da
qui "Who can apply", "Before you can apply", prossimo passo, produttori e
calendario. Ancora scoperto: promemoria via email (serve conservare gli
indirizzi: decide l'avvocato).
Domanda del 10 novembre 2026, "qual è la prima cosa che fa chi vuole fare un
film?": nessuno studio lo misura (cercato in inglese e in italiano). Le fonti
dicono: il primo film di solito si paga con soldi di chi crede in te (Stephen
Follows, 28 ottobre 2026: "Your first film will probably be funded");
esperienza in corti o TV va con più possibilità di un secondo film (Follows,
19 agosto 2026, senza dire che ne sia la causa); le guide consigliano di
partire da un corto. Da qui il passo "Make a short first". Per sapere la
risposta vera: chiederlo ai filmmaker della prova con persone reali.

## Sicurezza

- `analyze.js` accetta solo `{project}`: i prompt si costruiscono sul server
  (`_util/freePrompts.js`). Mai accettare testo di prompt dal browser.
- `sanitizeProject` (`_util/project.js`): solo campi noti, lunghezze come i
  `maxlength` del modulo.
- `start-full-report` firma id+email+progetto (`payloadSig.js`), la funzione
  in background rifiuta firme non valide; massimo 5 report al giorno per
  email, 3 ogni 3 ore per IP, anteprime 10 l'ora per IP. IP mai salvati in
  chiaro (HMAC).
- Errori 500 generici al client, dettagli solo in `console.error`.
  `admin-stats.html` manda la chiave nell'header `X-Admin-Key`.
- Netlify pubblica tutta la cartella (`publish = "."`): CLAUDE.md, funzioni,
  package*.json, `.claude/`, `.playwright/`, `.impeccable/` sono chiusi con
  404 in `netlify.toml`. Ogni nuovo file non del sito alla radice va
  aggiunto lì.

## Legale (in sospeso: Antonio sente un avvocato)

Antonio NON ha partita IVA. Privacy incompleta rispetto al GDPR art. 13
(titolare, basi giuridiche, trasferimenti USA, tempi di conservazione,
reclamo al Garante). NON scrivere il nome di Antonio sul sito finché non
decide. Oggi si conservano senza scadenza report + email e l'indice My
Reports; proposte in attesa: cancellazione dopo 30 giorni e niente My
Reports ("strada A") oppure report solo a schermo ("strada B"). Da valutare:
AI Act art. 50(2), domicilio ex D.Lgs. 70/2003 art. 7. Privacy e termini si
riscrivono dopo l'avvocato. Scheda per l'avvocato ricavata dal codice: doc
privato "Scheda dati OneCiak per l'avvocato"
(claude.ai/artifact/Y776k28X7HyxzMxcQgNXDX); i fatti nella privacy oggi
corrispondono al sito, restano le parti legali.

## Marketing

- Google indicizza già il sito (confermato da Antonio). WebSearch non è Google.
- Agente del lunedì (Routine `trig_01LhjUc5ZkrXiqCkiqh5hiKo`, lunedì 8:52 ora
  italiana): apre con il "punto della situazione" (il sito in breve, cosa è
  cambiato in settimana dal git log di main, le 3 cose da fare prese da
  "Cosa manca" qui sotto: tenerla aggiornata), controlla il sito, prepara 3
  post come Artifact privato. Non può fare push e non pubblica.
- Canali verificati: r/Screenwriting vieta contenuti AI, r/Filmmakers vieta
  i post solo-link.

## Cosa manca, in ordine

1. Avvocato: privacy, strada A o B, nome di Antonio. Poi riscrivere privacy e
   termini.
2. Prima del lancio: decidere il tetto di spesa Anthropic e ricaricare il
   credito (22,02 $ il 9 novembre, circa 55 report completi; dopo le prove
   del 10 novembre è più basso). Prova dal vivo fatta da Antonio l'8
   novembre 2026 su iPhone (The Salt Road): report arrivato, mittente vero
   `reports@report.oneciak.com`.
3. Prova con 20-30 filmmaker veri (per esempio una scuola di cinema) prima
   della pubblicità: quanti chiedono il report completo, quanti lo aprono,
   quanti fanno davvero qualcosa; e chiedere "qual è la prima cosa che hai
   fatto quando hai deciso di fare il tuo film?".
4. Lancio (Product Hunt, Reddit, scuole): dopo l'avvocato e la prova, con
   la frase di Antonio sul "perché" e una data; ogni testo lo approva lui.

## Controlli (da rifare dopo ogni modifica visibile o pulizia)

- **Giro completo sul sito vero**: 9 viste (home, menu, modulo, report di
  esempio con tutto aperto, My Reports, roadmap, privacy, termini, 404) × 6
  larghezze (262, 320, 393, 430, 1280, 1600) × chiaro/scuro/senza
  preferenza. Cercare: errori JS, richieste fallite, pagina più larga dello
  schermo, testo azzurro Safari, trattini lunghi, testi affiancati non
  allineati (quelli andati a capo uno sotto l'altro vanno bene, ma guardarli).
- **Funzioni**: modulo vuoto (7 caselle rosse), nuvoletta del glossario che si
  apre e si chiude, scaletta che cambia con il progetto (primo film, produttore
  già presente, film finanziato, corto), copia
  email produttori, PDF scaricato, calendario nascosto senza date, una
  analisi vera su `/.netlify/functions/analyze` (NON start-full-report).
- **Pulizia**: confronto pixel per pixel prima/dopo (server locale col codice
  vecchio da `git archive HEAD` su un'altra porta) su 8 viste × telefono e
  computer × 3 schemi: deve dare 0 differenze.
- **Link esterni** del report di esempio e della roadmap: tutti 2xx/3xx. Il
  regolamento di Locarno ha un controllo anti-robot Cloudflare (403): non
  verificabile da qui, va aperto a mano.

## Strumenti

- **Impeccable** (`.claude/skills/impeccable`): scanner di anti-pattern, gira
  in locale senza rete. Hook in `.claude/settings.local.json` dopo ogni
  Edit/Write e su Stop. Comando:
  `.claude/skills/impeccable/scripts/impeccable detect index.html`. Falsi
  positivi documentati con motivo in `.impeccable/config.json`.
- **Emil Kowalski design-eng** (`.claude/skills/emil-design-eng`, da
  github.com/emilkowalski/skills commit c8a7962, MIT, solo testo): regole per
  animazioni e reazioni al tocco.
- **Playwright**: script a mano con `NODE_PATH=/opt/node22/lib/node_modules
  node script.js` (sempre funzionante). Playwright CLI
  (`.claude/skills/playwright-cli`, `@playwright/cli` 0.1.22): reinstallare a
  ogni sessione con `npm install -g @playwright/cli@0.1.22`, config in
  `.playwright/cli.config.json`. Playwright MCP in `.mcp.json`.
- Server locale: `nohup setsid python3 -m http.server 8143 --directory
  /home/user/oneciak > log 2>&1 < /dev/null & disown` (muore tra un messaggio
  e l'altro: ricontrollare prima di usarlo). Test e script stanno nello
  scratchpad e si perdono a fine sessione.
- Per caricare le funzioni del server in locale serve `@netlify/blobs`:
  installarlo in una cartella dello scratchpad e usare `NODE_PATH`.
- Scartati: Taste, awesome-claude-design, Context7, Graphify, 21st MCP,
  Agent Skills. Strix (test di sicurezza AI) rimandato: servirebbe una chiave
  e un tetto di spesa decisi da Antonio, solo sulla preview.
