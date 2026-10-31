# OneCiak: contesto per Claude

Letto a ogni nuova sessione. Le sessioni non condividono memoria: qui c'è
quello che vale OGGI. Riordinato il 2026-10-29 (tolte le versioni superate;
la storia completa è nella cronologia git di questo file).

## Il progetto

OneCiak (oneciak.com) dà a filmmaker indipendenti un'analisi di mercato del
loro progetto: anteprima gratuita veloce, poi report completo gratuito via
email. Target: registi al primo film, sceneggiatori, produttori indipendenti,
neolaureati. Prendono decisioni vere di tempo e soldi: deve essere credibile e
utile davvero, non "carino".

Founder: **Antonio Brasile** (ragazzo). Scrive in italiano, informale, spesso
con typo quando è frustrato: non vuol dire che vuole un tono più formale.

- Repo `antoniobr97-a11y/oneciak`, branch di lavoro
  `claude/website-completion-aesthetics-6wknns`, base `main`.
- `index.html` è tutta l'app (CSS in `<style>`, poi HTML, poi JS).
- Backend: Netlify Functions in `netlify/functions/`. Deploy automatico su
  push a `main`. Niente Figma: tutto fatto in codice.

## Regole di Antonio (non derogabili)

0. **Come parlargli** (2026-10-29): sempre in italiano, anche i messaggi brevi
   e quelli di avanzamento ("sto facendo..."); parole semplici, niente gergo
   tecnico; risposte corte, non allungarsi. Restano in inglese solo i testi
   del sito, che è in inglese.
1. **Tutto verificato alla fonte** (2026-10-19 e 2026-10-20: "fonti
   verificate e mai cazzate, pensarci 100 volte"). Prima di affermare un fatto
   verificarlo davvero (comando, pagina ufficiale aperta, misura sui pixel) e
   dire da dove viene. Mai dedurre da uno strumento che non misura quella cosa
   (WebSearch non è Google, Chromium non è Safari, locale non è live): se non
   posso verificare, dirlo. Niente numeri a memoria. Se due fonti non
   concordano, dirlo. Persone/studi da consigliare: solo se verificati su
   registri ufficiali, e dire che esistere non vuol dire essere bravi. Meglio
   corto e sicuro. Se sbaglio, dirlo subito e correggere.
2. **Ogni contenuto promozionale lo vede prima lui** (post, Product Hunt,
   Reddit, email a scuole/riviste, nuove guide): testo esatto e anteprima, poi
   il suo ok esplicito. Né Claude né l'agente del lunedì postano o inviano.
3. **Mai trattini lunghi (—)** nei testi che gli scrivo e nel prodotto: usare
   virgole o punti.
4. **Dimostrare le modifiche**: screenshot prima/dopo, misure sui pixel, numeri.
   "Non vedo differenze" vuol dire che devo mostrarlo meglio.
5. **Cambi visivi grossi**: anteprima e attendere l'ok. Fix piccoli o tecnici
   (bug, contrasto, accessibilità, cose che ha chiesto lui puntualmente) si
   pubblicano subito. "Fai", "procedi", "vai", "pubblica" = via libera.
6. Domande esplorative ("che altro si può fare?"): risposta breve con una
   raccomandazione, non elenchi infiniti.
7. **Onestà**: mai inventare o gonfiare numeri mostrati agli utenti (il
   contatore "report generati" è stato tolto invece di falsificarlo). Link
   sempre verificati (`_util/linkCheck.js` per i report).
8. Vuole un sito da designer vero, non "da AI": niente tutto centrato, card
   identiche, bottoni a pillola, gradienti speculari, spinner generici,
   etichette sopra i titoli.

## Pubblicare su main (procedura obbligatoria)

Il 2026-10-04 un merge via API GitHub è risultato VUOTO (sito vecchio per 25
minuti). Quindi mai merge di PR, sempre:
```bash
git fetch origin main
git checkout -B main-fixN origin/main
git cherry-pick <sha-sul-branch>       # o checkout dei file dal branch
git diff origin/main --stat            # deve essere NON vuoto, altrimenti STOP
git push origin main-fixN:main
git checkout claude/website-completion-aesthetics-6wknns
```
Poi `mcp__github__get_commit` sul commit: deve avere additions/deletions
reali. Poi, in background, ciclo su `curl https://oneciak.com/?x=$i` che
cerca una stringa NUOVA del codice (su UNA riga sola, non spezzata da un a capo)
finché la trova: la CDN può servire la versione vecchia con status 200.

## Design attuale (deciso da Antonio, pubblicato)

**Chiaro e scuro seguono il dispositivo** (`prefers-color-scheme`), niente
pulsante. Blocchi CSS "LIGHT AND DARK" in fondo agli stili di index.html e in
fondo a `guides/guides.css`; anche privacy, termini, 404.
- **Scuro**: nero prugna `--night:#140d10` ovunque. UNA sola luce fissa allo
  schermo (`body::before`): petrolio a sinistra + rosso in basso a destra, con
  grana. Antonio: "qui è stupendo il nostro colore, facciamolo uguale ovunque".
- **Chiaro**: bianco vero `#ffffff` ("quando è bianco deve essere bianco, non
  quel grigino"), stessa composizione dello scuro fissa allo schermo: petrolio
  reso luminoso `#407381` a bassa opacità a sinistra + rosso morbido in basso a
  destra. Niente grana. Testo grigio piccolo `#3a3a3a`, rosso errori `#8a2419`.
- **Senza preferenza**: vecchio stile (hero scuro con bagliori ambra/arancio/
  rosso/vino e petrolio, sfumatura `in oklab` verso la carta `--paper:#f4f1ec`,
  satinato con grana nelle parti chiare).
- **Font** self-hosted in `/fonts` (niente Google Fonts, GDPR; CSP
  `font-src 'self'` in `netlify.toml`): titoli **Geist**; testo e anche dati
  piccoli **Carlito** (al posto di Calibri, che serve licenza; `size-adjust:
  112%`). Inter, Inter Tight, IBM Plex Mono non si usano più (file ancora in
  /fonts). Mail: Calibri, Carlito, Arial. PDF: `fonts/carlito-*-pdf.ttf`
  caricati al clic, Helvetica di riserva. Raptor Text gli piaceva ma è a
  pagamento: non usarlo senza licenza.
- Regole: bottoni `border-radius: 10px`; testo allineato a sinistra; colori
  ambientali asimmetrici; hover solo dentro `@media (hover: hover) and
  (pointer: fine)`; ogni cliccabile ha `:active` con `scale(...)`; su touch
  le aree cliccabili piccole sono allargate a ~44px senza cambiare l'aspetto.
- Niente etichette sopra i titoli (eyebrow) né numeri decorativi (01-07,
  01-05): tolti ovunque. Le etichette sono parole in Carlito grassetto. Icone
  disegnate (chevron, spunta), non simboli di testo.
- Banner cookie: NON serve (nessun cookie né tracker, statistiche anonime
  self-hosted; localStorage solo per il login My Reports scelto dall'utente).
  Il disclaimer con casella sulla landing resta obbligatorio (`termsCheck`).
- **Contrasto**: misurarlo sui pixel veri (nascondere il testo con
  `:is(#zz,html) *{color:transparent!important}`: senza `:is(#zz,html)` le
  regole `!important` del sito vincono e il controllo dà falsi 1.0:1).
  Testo piccolo almeno 4.5:1, titoli grandi almeno 3:1. Impeccable sui
  gradienti dà falsi positivi.

**Bocciato da Antonio, NON riproporre**: fasce grigio-azzurre/rosa da vetro
smerigliato; "ora d'oro"; luce parassita da destra (varianti A/B/C del chiaro);
macchia rossa/ambra in alto a destra nelle intestazioni; altre varianti di
satinato/grana ("va bene così basta"); palette "intensa" e "Warm Neutrals";
il redesign proposto da Taste (sito vestito da carte di produzione, ciak
nell'intestazione, foto d'archivio, logo gigante nel footer); la sesta/settima
area del report; il PDF "One-page summary"; il pulsante "Next" tra le aree;
scritte rosse sotto ogni casella del modulo.

## Pagine e flusso

- **Home**: compatta ("troppo piena, niente ripetizioni"): niente CTA finale
  ripetuta, niente link doppi al report di esempio. Navbar trasparente, poi
  vetro, poi chiara (`updateLandingNav()`). Scheda del report di esempio in
  vetro con i voti veri di Northbound.
- **Modulo**: niente card, sezioni separate da una linea. "Where you are":
  fase (obbligatoria), chi produce, durata, già mostrato. Campi a 16px su
  touch (iOS non zooma). Campi obbligatori vuoti: SOLO bordo rosso sulla
  casella (`markMissing`, `REQUIRED`), anche quando è selezionata, nessuna
  scritta sotto, la pagina sale al primo vuoto senza mettere il cursore; sotto
  il bottone "N fields are missing, marked in red above.". Le caselle di testo
  sono alte quanto il loro testo di esempio, misurato sul dispositivo
  (`fitPlaceholders`).
- **Caricamento**: 5 dimensioni che avanzano invece di uno spinner
  (`startLoadingDims` / `finishLoadingDims` / `resetLoadingDims`), titolo del
  film, allineato a sinistra.
- **Report completo** (riorganizzato il 2026-10-28, "troppo incasinato"):
  titolo, voto nella scheda di vetro, riassunto (4 righe + "Read more" su
  telefono), rischio e opportunità; "Your next step" (`buildNextStep`: una
  sola azione per questa settimana, perché, cosa avere pronto); SOLO le 5
  aree con voto; poi "Your plan"
  (`buildPlanSection`, fasi in ordine) e il link alla roadmap. Una sola area
  aperta alla volta, la riga toccata resta ferma (`toggleAccordion`). Indice
  delle aree che segue lo scorrimento (`mountAreaNav`: colonna da 1360px,
  barra sotto). Dentro un'area: giudizio (prima frase + "Read more"),
  "What to do" (prima frase di ogni consiglio + "More"), nell'area Financial
  il blocco "Before you can apply" e "Producers to contact" aperto
  (`buildProducers`: produttori veri con film, come accettano progetti,
  fonte, e una bozza di email con tasto "Copy the email"), poi tutto chiuso in righe con la STESSA
  freccia (Red flags and strengths, Next 90 days, liste con fonti). Le liste
  stanno nella loro area: Festival calendar e Awards in Festival; Sales
  agents, mercati, ricavi in Distribution; Legal in Creative. Business plan e
  lista rischi solo nel PDF. In fondo: How to read, Glossary, un solo bottone
  "Download the full report", "Add the deadlines to your calendar" (.ics fatto
  nel browser, promemoria 7 giorni prima, nascosto senza date future).
- **Report di esempio Northbound**: report VERO del motore (voto 5.0), fonti
  controllate il 23 ottobre 2026. TorinoFilmLab chiude il 5 novembre 2026:
  dopo quella data la voce va aggiornata.
- **`/roadmap/`**: 9 fasi, 49 lavori con spunta (solo nel browser,
  `oneciak-roadmap-v1`), 27 citazioni verificate parola per parola il
  2026-10-24. Pensata per i film, non per le serie. Il report collega la fase
  del progetto (`STAGE_TO_ROADMAP`). Se cambia una regola citata, ricontrollare.
- **Guide** in `/guides/` (CSS `guides/guides.css`, da tenere allineato al
  sito). Nuove guide: aggiungere a `guides/index.html` e `sitemap.xml`, dati e
  link verificati.

## Motore dei report

- Modello `claude-haiku-5-5` (anteprima effort `low`), ricerca web Anthropic:
  anteprima 2 ricerche, report completo fino a 22 (sezioni B-E di
  `reportPrompts.js`). Costi misurati il 2026-10-22: anteprima ~0,025 $,
  report completo ~0,22-0,24 $. Limite di spesa Anthropic: 50 al mese (con la
  pubblicità circa 200 report completi; poi le analisi falliscono fino al mese
  dopo: da decidere con Antonio prima del lancio).
- `grounding.js`: una voce (fondo, festival, film, agente, piattaforma) resta
  solo se la sua fonte è tra i risultati della ricerca di quella richiesta;
  date e cifre solo se sono sulla pagina; niente cifre da aggregatori;
  scadenze passate "Closed (...)" una volta sola; `rule_quote` resta solo se è
  sulla pagina parola per parola (i PDF non si leggono: le citazioni da PDF
  cadono); `applicant` (chi può fare domanda) resta solo con la sua
  `rule_quote`.
- `verifiedFacts.js`: fatti controllati A MANO, da ricontrollare quando cambia
  la legge. Tax credit italiano 30% per produttori indipendenti, tetto 4 mln
  (D.I. MiC-MEF 6/7/2026 n. 281). Bando MiC contributi selettivi 2026
  (d.d. 15/5/2026 n. 1238): scrittura = autori persone fisiche, opere oltre
  52 min, in italiano, no IA; sviluppo e produzione = solo imprese
  indipendenti italiane Ateco 59.1 con un'opera negli ultimi 5 anni (salvo
  società nuove). `applySelective` sistema queste righe (anche 'Split').
- SOLO FILM (Antonio, 2026-10-30): lungometraggi e cortometraggi, documentari
  compresi. Niente serie (tolte da modulo e prompt; i vecchi report di serie
  si vedono ancora).
- Produttori in ogni paese (2026-10-30, "stessa qualità per chi usa OneCiak
  dalla Svezia o dalla Cina"): sezione G di `reportPrompts.js` (5 ricerche) +
  `checkNamed` in grounding.js: un produttore resta SOLO se la pagina della
  fonte contiene il suo nome (senza Srl/Ltd/AB...) E il titolo del film; un
  "film" uguale al nome dell'azienda viene scartato. Prova del 2026-10-30:
  Svezia 2, Cina 4, Italia 4 produttori veri. `next_step` nella sezione A.
- Prompt: `stageRules` (fase del progetto), rubrica `SCORING` (voto = media delle 5 aree), niente previsioni di
  incasso in euro né prezzi E&O. Ogni voce: "Source: dominio · checked data"
  su sito, PDF e mail.
- Fact-check sul sito live del 2026-10-22: anteprime 90% corrette, report
  completi 78%, 0 enti inventati (vecchio motore: 23%). Dal 2026-10-30
  `FULL_MAX_TOKENS` = 32000 (a 16000 una sezione si interrompeva a metà JSON e
  il report falliva: "Unexpected end of JSON input"). Problemi noti: regole
  di prima visione a volte parafrasate male, fondi senza scadenza scritta,
  qualche film di confronto poco pertinente, a volte fonti da aggregatori
  (es. asianfilmfestivals.com per Locarno), nei corti spesso nessun film di
  confronto (regola severa, voluto). Costo del report con i produttori: da
  misurare sui primi report veri.
- **Prove**: PR bozza #81 (`test-sourced-reports`) = anteprima
  `deploy-preview-81--oneciak.netlify.app`, genera i report sulla preview.
  Ha commit "TEST ONLY" (mostra sempre il motivo dell'errore, limite 12;
  `CONTEXT` NON esiste mentre girano le funzioni): MAI su main, la
  PR non va mai mergiata. Per aggiornarla: checkout dei file dal branch di
  lavoro sopra `origin/test-sourced-reports`. Mail di prova a
  `delivered+X@resend.dev` (non arrivano a nessuno).

## Ricerca "come si fa davvero un film" (2026-10-28)

Doc privato "Come si fa davvero un film: ricerca per OneCiak"
(claude.ai/artifact/JrLNDdn3koDmXdo6Lv3MuH). Punti chiave verificati: solo il
25,3% degli esordienti fa un secondo film entro 5 anni (Follows 2026); in
Italia senza società di produzione niente fondi per sviluppo e produzione;
le serie passano da bibbia, pilota e mercati di coproduzione (servono
società). Da qui "Who can apply", "Before you can apply", regole per le serie
e calendario; poi (2026-10-30) solo film, prossimo passo e produttori. Ancora
scoperto: promemoria via email
(serve conservare gli indirizzi: decide l'avvocato).

## Sicurezza

- `analyze.js` accetta solo `{project}`: i prompt si costruiscono sul server
  (`_util/freePrompts.js`). Mai accettare testo di prompt dal browser.
- `sanitizeProject` (`_util/project.js`): solo campi noti, lunghezze come i
  `maxlength` del modulo.
- `start-full-report` firma id+email+progetto (`payloadSig.js`), la funzione
  in background rifiuta firme non valide; massimo 5 report al giorno per
  email, 3 ogni 3 ore per IP. IP mai salvati in chiaro (HMAC).
- Errori 500 generici al client, dettagli solo in `console.error`.
  `admin-stats.html` manda la chiave nell'header `X-Admin-Key`.
- Netlify pubblica tutta la cartella (`publish = "."`): CLAUDE.md, funzioni,
  package*.json, `.claude/`, `.playwright/` sono chiusi con 404 in
  `netlify.toml`. Ogni nuovo file non del sito alla radice va aggiunto lì.

## Legale (in sospeso: Antonio sente un avvocato)

Controllo su fonti ufficiali del 2026-10-19. Antonio NON ha partita IVA.
Privacy incompleta rispetto al GDPR art. 13 (titolare, basi giuridiche,
trasferimenti USA, tempi di conservazione, reclamo al Garante). NON scrivere
il nome di Antonio sul sito finché non decide. Oggi si conservano senza
scadenza report + email e l'indice My Reports; proposte in attesa:
cancellazione dopo 30 giorni e niente My Reports ("strada A") oppure report
solo a schermo ("strada B"). Da valutare: AI Act art. 50(2), domicilio ex
D.Lgs. 70/2003 art. 7. Privacy e termini contengono ancora trattini lunghi:
si riscrivono dopo l'avvocato.

## Marketing

- Google indicizza già il sito (confermato da Antonio). WebSearch non è Google.
- Agente del lunedì (Routine `trig_01LhjUc5ZkrXiqCkiqh5hiKo`, lunedì 8:52 ora
  italiana): controlla il sito, prepara 3 post e una bozza di guida come
  Artifact privato. Non può fare push e non pubblica. Quando Antonio dice
  "pubblica la bozza guida": leggere l'Artifact, riverificare fonti e link,
  CSS come `<link href="/guides/guides.css">`, salvare in
  `guides/<slug>/index.html`, aggiornare indice guide e sitemap, anteprima,
  procedura di pubblicazione.
- Canali verificati consegnati il 2026-10-19 (r/Screenwriting vieta contenuti
  AI, r/Filmmakers vieta i post solo-link).

## Cosa manca, in ordine

1. Avvocato: privacy, strada A o B, nome di Antonio. Poi riscrivere privacy e
   termini.
2. Prima del lancio: decidere il tetto di spesa Anthropic; prova completa dal
   vivo (modulo, report, mail, mittente vero e non "onboarding@resend.dev",
   iPhone vero).
3. Lancio (Product Hunt, Reddit, scuole): dopo l'avvocato, con la frase di
   Antonio sul "perché" e una data; ogni testo lo approva lui.
4. Northbound da aggiornare dopo il 5 novembre 2026 (TorinoFilmLab); il
   report di esempio non ha ancora "Your next step" né produttori.

## Strumenti

- **Impeccable** (`.claude/skills/impeccable`): scanner di anti-pattern, gira
  in locale senza rete (verificato con strace). Hook in
  `.claude/settings.local.json` dopo ogni Edit/Write e su Stop. Comando:
  `.claude/skills/impeccable/scripts/impeccable detect index.html`. Falsi
  positivi documentati con motivo in `.impeccable/config.json`: non toglierli.
- **Playwright CLI** (`.claude/skills/playwright-cli`, `@playwright/cli`
  0.1.22, Apache-2.0, Microsoft): reinstallare a ogni sessione con
  `npm install -g @playwright/cli@0.1.22`, `NO_UPDATE_NOTIFIER=1`, config in
  `.playwright/cli.config.json`.
- **Playwright MCP** in `.mcp.json` con `--executable-path
  /opt/pw-browsers/chromium --headless`. Se non c'è: script Playwright a mano
  con `NODE_PATH=/opt/node22/lib/node_modules node script.js` (sempre
  funzionante).
- Server locale: `nohup setsid python3 -m http.server 8143 --directory
  /home/user/oneciak > log 2>&1 < /dev/null & disown` (con `&` semplice
  muore quando cambia la cartella). Test e script stanno nello scratchpad e
  si perdono a fine sessione.
- Tolti o scartati: Taste (2026-10-27, "è una merda"), awesome-claude-design,
  Emil Kowalski design-eng (mai stato nel repo). Valutati il 2026-10-29 e
  non installati: Context7, Graphify, 21st MCP (componenti "da AI"), Agent
  Skills (già le usiamo); Strix (test di sicurezza AI) rimandato, servirebbe
  una chiave e un tetto di spesa decisi da Antonio, solo sulla preview.
