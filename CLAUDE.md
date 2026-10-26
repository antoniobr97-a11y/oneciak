# OneCiak — contesto per Claude

Letto automaticamente a ogni nuova sessione in questa cartella. Scritto perché
le sessioni non condividono memoria tra loro — questo file è il modo per non
dover riscoprire da capo le stesse cose.

## Cos'è il progetto

OneCiak (oneciak.com) è uno strumento AI che dà a filmmaker indipendenti
un'analisi di mercato per il loro progetto (genere, budget, pubblico,
distribuzione) — un'anteprima gratuita veloce, poi un report completo gratuito
via email. Target: registi al primo film, sceneggiatori, produttori
indipendenti, neolaureati in scuole di cinema — persone che prendono decisioni
reali di tempo/denaro basandosi su questo, quindi deve risultare credibile,
non gimmicky.

Il founder è **Antonio Brasile** (ragazzo, non dare per scontato altro).
Comunica in italiano, informale, spesso con typo/maiuscole quando è
frustrato — non è un segnale di voler un tono più formale, il contrario.

- Repo: `antoniobr97-a11y/oneciak`, branch di lavoro
  `claude/website-completion-aesthetics-6wknns`, base `main`.
- `index.html` è l'intera app (un solo file enorme — CSS in `<style>` in
  testa, poi HTML, poi tutto il JS in `<script>` in fondo).
- Backend: Netlify Functions in `netlify/functions/`. Deploy automatico su
  push a `main` (Netlify ascolta il repo).
- Niente Figma: il sito è sempre stato costruito direttamente in codice, mai
  partito da un design visivo esterno.

## Come comunica l'utente — leggere prima di scrivere testo

- **Mai trattini lunghi (—)** nei testi che gli mostro o che scrivo nel
  prodotto quando me lo chiede esplicitamente — usare virgole o punti. Gliel'ho
  sentito dire chiaramente, non è un dettaglio.
- Non crede alle modifiche "a occhio" — se dico che qualcosa è cambiato devo
  **dimostrarlo**: screenshot prima/dopo, misurazione pixel reale (PIL/numpy),
  o un numero concreto. "Non vedo differenze" è una reazione comune a modifiche
  sottili anche quando sono reali — non vuol dire che ho sbagliato, vuol dire
  che devo mostrarlo meglio.
- Vuole un sito che sembri fatto da un designer vero, non "da AI" — diffida di:
  tutto centrato, card ovunque identiche, bottoni a pillola piena, gradienti
  perfettamente speculari/bilanciati, spinner generici. Vedi sezione Design
  sotto per cosa è già stato corretto.
- Quando chiede "che altro si può fare" è una domanda esplorativa — rispondere
  breve con una raccomandazione, non un elenco infinito. Quando dice "fai",
  "procedi", "vai" è via libera a eseguire senza richiedere altra conferma.
- Prima di pubblicare un cambiamento visivo importante, mandare
  screenshot/anteprima e aspettare conferma — l'ha chiesto esplicitamente.
  Cambiamenti piccoli/tecnici (bug fix, contrasto, accessibilità) si pubblicano
  senza aspettare.

## REGOLA DI ANTONIO (2026-10-19, non derogabile): tutto verificato alla fonte

"Ogni cosa che mi dici deve essere certificata alla fonte e corretta. Non
sbagliare più, metti solo confusione." Nata dopo che gli ho detto che Google
non indicizzava il sito basandomi su WebSearch (che NON è Google): era falso.
In pratica:
- Prima di affermare un fatto (su sito, codice, servizi esterni, dati,
  regole) verificarlo direttamente: comando eseguito, pagina ufficiale aperta,
  misura sui pixel. Dirgli da dove viene ("verificato su ...").
- Mai dedurre una conclusione da uno strumento che non misura davvero quella
  cosa (es. WebSearch per Google, Chromium per Safari, test locale per live).
  Se non posso verificarlo, dirlo chiaro: "non verificato, perché ...".
- Niente supposizioni presentate come fatti, niente numeri a memoria.
- Se scopro un mio errore, dirlo subito e correggerlo.

## REGOLA FISSA PER SEMPRE (ribadita da Antonio il 2026-10-20)

"Fonti verificate e mai cazzate, pensarci 100 volte prima di dirmi una
cosa." Si aggiunge alla regola sopra e vale per OGNI risposta:
- Ricontrollare due volte prima di rispondere: la fonte dice davvero quello
  che sto per scrivere? È attuale? È la fonte primaria (ufficiale) o una
  copia? Se due fonti non concordano, dirlo invece di sceglierne una.
- Per persone, studi, aziende da consigliare (es. avvocati, commercialisti):
  verificarne l'esistenza su registri ufficiali (albo dell'Ordine, sito
  ufficiale dello studio) e riportare solo quello che le fonti dicono. Mai
  inventare specializzazioni, recensioni, prezzi o contatti. Dire chiaramente
  che verificare l'esistenza non equivale a garantire la qualità.
- Meglio una risposta più corta e sicura che una lunga con cose non
  controllate. Se non sono sicuro, lo dico.

## REGOLA DI ANTONIO (2026-10-19): ogni pubblicità la vede prima lui

Post social, testi per Product Hunt / Reddit / Hacker News, email a scuole o
riviste, nuove guide, qualsiasi contenuto promozionale: prima si mostra ad
Antonio il testo esatto (e l'anteprima visiva se c'è), poi si aspetta il suo
ok esplicito. Claude e l'agente del lunedì non postano, non inviano email e
non pubblicano mai contenuti promozionali da soli: preparano, Antonio decide.

## Bug critico di infrastruttura: il merge via API GitHub a volte è vuoto

**Scoperto il 2026-10-04, importantissimo.** La PR #79 è stata creata e
"mergiata" con successo tramite `mcp__github__merge_pull_request`, ma il
commit risultante aveva **zero righe di diff reale** (`git show <sha> --stat`
non mostrava nulla) — GitHub aveva calcolato il merge contro una base
sbagliata/obsoleta. Il sito è rimasto con la versione vecchia per ~25 minuti
mentre sembrava tutto a posto.

**Procedura corretta adottata da allora per OGNI pubblicazione su `main`:**
```bash
git fetch origin main
git checkout -B main-fixN origin/main
git cherry-pick <sha-del-commit-sul-branch-feature>
git diff origin/main --stat   # deve mostrare un diff NON vuoto, altrimenti STOP
git push origin main-fixN:main
git checkout claude/website-completion-aesthetics-6wknns
```
Poi **verificare sempre** con `mcp__github__get_commit` (detail:"stats") che
il commit su `main` abbia `additions`/`deletions` reali prima di dire
all'utente che è pubblicato. Non fidarsi mai del solo "merged: true" di una
PR — l'ho visto mentire.

**Dopo il push**, il deploy Netlify richiede qualche minuto. Verificare con un
loop che cerca una stringa specifica e NUOVA nell'HTML live (non solo che il
sito risponda 200 — a volte la CDN serve una versione cache stantia anche con
status 200):
```bash
i=0
while [ $i -lt 40 ]; do
  out=$(curl -s --fail https://oneciak.com/ 2>/dev/null)
  if [ -n "$out" ] && echo "$out" | grep -q "STRINGA-UNICA-DEL-NUOVO-CODICE"; then
    echo "NEW VERSION LIVE at attempt $i"; break
  fi
  i=$((i+1)); sleep 15
done
```
Farlo girare in background (`run_in_background: true`), non bloccare la
conversazione aspettando.

## Design — decisioni prese, non ripartire da zero

**Redesign del 2026-10-08 (approvato da Antonio, pubblicato):** direzione
"sala buia" ispirata a A24/NEON/Stripe, scelta tramite mockup A/B.
- **Hero landing scuro** (`--night:#140d10`, nero prugna). **Palette attuale
  (variante "C", scelta da Antonio il 2026-10-08 da una sua immagine di
  riferimento "grain gradient")**: bagliori ai bordi in ambra `#eb893f`,
  arancio `#ec5828`, rosso `#e1241f`, vino `#8b1921` in alto a destra e in
  basso a destra, verde petrolio `#182b30` a sinistra, grana pellicola
  visibile (overlay 0.22). La colonna del testo resta su fondo scuro.
  Stessa palette (più piccola) su header risultati/My Reports e menu.
  Storia: prima nero caldo con bagliore 20% ("troppo marrone"), poi neutro
  ("troppo freddo"), poi via di mezzo, poi questa. Scartate anche le
  varianti "intensa" e "Warm Neutrals" (#eb5e28/#efece3/#2c2324).
  Il nero **sfuma** nel crema
  (`--paper:#f4f1ec`) in ~280px, senza linea netta. La sfumatura è
  interpolata `in oklab` (variante "B" scelta da Antonio il 2026-10-08): la
  versione a gradini nei grigi faceva una fascia "color fango" che non gli
  piaceva. Resta come fallback per browser vecchi. Antonio odia gli
  "stacchi" tra sfondo e contenuto: niente bordi netti, niente card bianche
  incollate sullo sfondo. La sfumatura è nel `padding-bottom` dell'hero, sotto
  tutto il testo (così il testo non finisce mai sui toni intermedi).
  **La sfumatura finisce trasparente** (non su `--paper` pieno) e bagliori +
  grana dell'hero sfumano con `mask-image` negli ultimi 220px: così sotto si
  vede la stessa texture del resto della pagina. Prima c'era una riga
  visibile (crema liscio sopra, carta con grana sotto, rosso tagliato di
  netto). Segnalato da Antonio il 2026-10-10, non tornare indietro.
- **Parti chiare satinate, non "carta"** (scelto da Antonio il 2026-10-10
  da una sua immagine di riferimento): `body::before` = riflessi larghi e
  morbidi (luce in alto a destra, ombra calda in basso a sinistra),
  `body::after` = grana fine uniforme (feTurbulence 1 ottava, opacity 0.22).
  La vecchia grana a fibre di carta è stata tolta.
  Provata e SCARTATA da Antonio (2026-10-10): grana forte calibrata sulla sua
  foto (std ~5.6, overlay) e versioni con nastro/pieghe di raso. Ha detto
  "va bene così basta": non riproporre altre varianti di satinato/grana. Il nastro curvo luminoso
  dello stesso riferimento è stato provato sull'hero ma NON scelto (per ora).
- **Scheda report di esempio in vetro scuro** (variante "B" scelta da lui, non
  quella chiara). Numeri veri dal report statico Northbound.
- **Font**: `--display` **Geist** (scelto da Antonio il 2026-10-08, "C" nel
  confronto; titoli principali in Bold 700, numeri grandi sottili). Gli
  piaceva il Raptor Text Bold ma è a pagamento: serve licenza web, non
  usarlo senza. Prima era Inter Tight. Inter per il
  testo, `--mono` IBM Plex Mono per le etichette piccole maiuscole.
  **Self-hosted in `/fonts`** (niente Google Fonts, per il GDPR). Il CSP in
  `netlify.toml` ha `font-src 'self'`: se si aggiunge un font esterno va
  cambiato anche lì, altrimenti viene bloccato.
- **Tutto il testo in Carlito** (scelto da Antonio il 2026-10-23, voleva Calibri;
  i titoli restano Geist, le etichette IBM Plex Mono): Calibri è di Microsoft,
  non scaricabile e serve licenza web, e non c'è su iPhone/Mac/Android; Carlito
  è OFL 1.1 con le stesse misure. Self-hosted in `/fonts` (400, 700, 400
  italic) con `size-adjust: 112%` perché a parità di px è ~15% più piccolo di
  Inter (misurato). Vale per index, guide, privacy, termini, 404. Mail:
  Calibri, Carlito, Arial.
- **Report leggibile** (2026-10-23, `paras()`, `rblock()`, `entry()` in
  index.html): paragrafi di 2 frasi con la prima in evidenza, rischi e punti di
  forza affiancati, consigli numerati, approfondimenti in tendine, fondi e
  festival con importo/scadenza separati. In cima i 5 voti (`areaOverview`),
  indice delle aree che segue lo scorrimento (`mountAreaNav`: colonna a
  sinistra da 1360px, barra sotto l'header sotto), piano 30/60/90 a linea del
  tempo. Un'area aperta è ~35% più corta di prima.
- **Modulo, sezione "Where you are"** (2026-10-23): fase del progetto
  (obbligatoria), chi produce, durata, già mostrato. I prompt adattano i
  consigli alla fase (`stageRules` in `reportPrompts.js`).
- **Report di esempio Northbound** (2026-10-23): ora è un report VERO del
  motore nuovo, con 35 correzioni dopo il controllo di ogni fonte; voto 5.0
  (non più 7.2 inventato). La scheda in home mostra i suoi voti reali.
- **Niente etichette sopra i titoli** (2026-10-24, "meno AI possibile" con
  Impeccable 4.7, craft floor: l'eyebrow sopra un titolo è vietato senza
  eccezioni): tolte "New analysis", "Market report", "My reports", "Guides",
  "404". Sulla guida al posto dell'etichetta c'è un breadcrumb vero
  (`.g-crumb`). Tolti anche i numeri 01-06 sui titoli della guida e "01"
  nell'indice guide. Restano apposta: i numeri 01-07 delle aree del report
  (servono a orientarsi nell'indice) e 01-05 del caricamento. Ignorati in
  `.impeccable/config.json` con motivo: low-contrast (falso positivo sui
  gradienti, minimo misurato sui pixel 5.69:1), Geist (scelto da Antonio),
  alone radiale del 404 (è la palette dell'hero). Non rimettere etichette.
- **Form senza card**: sezioni separate da una linea sottile e un numero mono,
  campi = tinta dello sfondo (`--field`), focus con anello arancio morbido.
- **Navbar landing**: trasparente, poi vetro scuro, poi carta chiara oltre la
  sfumatura (`updateLandingNav()`).
- **Banner cookie: NON serve** (verificato): nessun cookie, nessun tracker,
  statistiche anonime self-hosted; il localStorage serve solo al login
  "My Reports" scelto dall'utente. Non aggiungerlo senza un motivo nuovo.
- Il disclaimer con casella sulla landing resta obbligatorio (`termsCheck`).
- **Risultati e caricamento** (stesso giorno): header scuro che sfuma come la
  home, punteggio nella stessa scheda di vetro (`#overallScore` è dentro
  `.r-hero`), niente card, numeri mono. Home compattata su richiesta di
  Antonio ("troppo piena, niente ripetizioni"): non riaggiungere etichetta
  sopra il titolo, link doppi al report di esempio, CTA finale ripetuta.

Regole che restano valide:
- Contrasto: misurarlo sui **pixel veri** (nascondere il testo, campionare lo
  sfondo), non fidarsi solo di Impeccable: sui gradienti dà falsi positivi.
  Testo piccolo almeno 4.5:1, titoli grandi almeno 3:1.
- Bottoni: `border-radius: 10px`, mai pillola piena.
- Macchie di colore ambientali **asimmetriche**, mai speculari.
- Testo allineato a sinistra, non centrato.
- Hover dentro `@media (hover: hover) and (pointer: fine)`, ogni elemento
  cliccabile ha `:active` con `scale(...)`.
- Caricamento (`#sec-loading`): 5 dimensioni 01-05 che avanzano invece di uno
  spinner (`startLoadingDims` / `finishLoadingDims` / `resetLoadingDims`).

## Strumenti di design installati (2026-10-08)

- **Emil Kowalski design-eng** (`.claude/skills/emil-design-eng`, committato):
  skill di filosofia su animazioni/craft. Letta per intero, sicura.
- **Impeccable** (`.claude/skills/impeccable`, committato, ~20MB con binario):
  scanner automatico di anti-pattern di design. Gira **in locale, zero
  chiamate di rete** (verificato con `strace`). Hook configurati in
  `.claude/settings.local.json` girano dopo ogni Edit/Write e su Stop.
  Comando: `.claude/skills/impeccable/scripts/impeccable detect index.html`.
  Falsi positivi già documentati con motivazione in `.impeccable/config.json`
  (`ignores add-value <rule> "*" --file index.html --reason "..."`) — non
  cancellarli senza motivo, c'è scritto perché sono stati ignorati.
- **Taste**: era installata in `~/.claude/skills/taste`, ma **NON persiste**.
  Il container cloud è nuovo a ogni sessione e `~/.claude` viene azzerata
  (verificato il 2026-10-08: sparita insieme alla config MCP utente). Per
  averla stabile va messa nel repo in `.claude/skills/taste` e committata.
  Fonte originale da chiedere ad Antonio se serve reinstallarla.
- **Playwright MCP**: configurato a livello di progetto in `.mcp.json`
  (committato, così sopravvive al reset del container) con
  `--executable-path /opt/pw-browsers/chromium --headless`, perché il canale
  "chrome" di default non esiste in questo sandbox. Un server MCP aggiunto o
  cambiato si carica solo **all'avvio di una nuova sessione**. Se
  `mcp__playwright__*` non c'è o dà "chrome not found", usare intanto script
  Playwright a mano via Bash con `executablePath: '/opt/pw-browsers/chromium'`
  (metodo collaudato, funziona sempre).

## Test di regressione

In `/tmp/claude-0/.../scratchpad/` (si perdono a fine sessione — se servono
ancora, ricontrollare che esistano prima di lanciarli). Pattern tipico:
```bash
NODE_PATH=/opt/node22/lib/node_modules node test_nome.js
```
Server locale per testare prima di pubblicare:
```bash
(python3 -m http.server 8143 > /tmp/qualcosa.log 2>&1 &) ; sleep 2; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8143/index.html
```

## Sicurezza backend (revisione del 2026-10-08)

- `analyze.js` accetta **solo** `{project}`: i prompt dell'anteprima si
  costruiscono sul server (`_util/freePrompts.js`). Mai più accettare testo di
  prompt dal browser, altrimenti chiunque usa la chiave Anthropic per altro.
- Ogni progetto passa da `_util/project.js` (`sanitizeProject`: solo campi
  noti, lunghezze massime uguali ai `maxlength` del form).
- `start-full-report` firma id+email+progetto (`_util/payloadSig.js`);
  `generate-report-background` rifiuta payload con firma non valida. Tetto di
  5 report al giorno per indirizzo email (`checkKeyLimit`, email hashata).
- Errori 500 generici verso il client, dettagli solo in `console.error`.
- `admin-stats.html` manda la chiave nell'header `X-Admin-Key`, non nell'URL.
- Limite di spesa mensile nella console Anthropic: impostato a 50 (confermato da Antonio il 2026-10-08). Se si raggiunge, le analisi falliscono fino al mese dopo.

## Marketing e contenuti (dal 2026-10-19)

- **Sezione Guide** in `/guides/` (pagine statiche, CSS condiviso in
  `guides/guides.css` copiato dai token dell'app: se cambia il look del sito,
  aggiornarlo anche lì). Prima guida:
  `/guides/festival-strategy-first-film/`. Ogni dato verificato su fonti
  ufficiali e ogni link controllato prima di pubblicare. Nuove guide:
  aggiungerle a `guides/index.html` e `sitemap.xml`.
- **Agente del lunedì** (Routine `trig_01LhjUc5ZkrXiqCkiqh5hiKo`, lunedì 8:52
  ora italiana, notifica push+email ad Antonio): controlla il sito, prepara 3
  post e la bozza della guida successiva come **Artifact privato** (pagina di
  anteprima). Le sessioni avviate da una Routine NON possono fare push: lo
  strumento add_repo lì non esiste (verificato il 2026-10-19, ToolSearch "No
  matching deferred tools found", git push 403). Non pubblica mai. Quando
  Antonio dice "pubblica la bozza guida" con il link: leggere l'Artifact
  (Artifact action read), riverificare fonti e link, rimettere il CSS come
  `<link href="/guides/guides.css">`, salvare in `guides/<slug>/index.html`,
  aggiornare `guides/index.html` + `sitemap.xml`, mostrargli l'anteprima e
  pubblicare con la solita procedura.
- **Google indicizza già il sito** (confermato da Antonio il 2026-10-19). Lo
  strumento WebSearch di Claude NON è Google: se non trova oneciak.com non
  vuol dire che Google non lo conosca. Search Console resta utile per i dati
  (query, clic), non per "farsi trovare".
- Lista canali di promozione verificata (community con regole
  sull'autopromozione, directory, scuole, riviste): consegnata ad Antonio il
  2026-10-19. r/Screenwriting vieta contenuti AI; r/Filmmakers vieta i post
  solo-link.

## Questioni legali (in sospeso dal 2026-10-19, Antonio sente un avvocato)

Controllo fatto su fonti ufficiali il 2026-10-19 (GDPR, AI Act + Reg. UE
2026/1744, linee guida cookie Garante, D.Lgs. 70/2003, DPR 633/72 art. 35,
Codice del Consumo, L. 132/2025, termini Anthropic, Google Search Central).
- Antonio NON ha partita IVA: niente P.IVA sul sito.
- Privacy incompleta rispetto a GDPR art. 13: manca titolare (identità e
  contatti), basi giuridiche, trasferimenti USA (Netlify/Resend nel DPF,
  Anthropic con SCC del suo DPA), tempi di conservazione, diritto di reclamo
  al Garante. Antonio ha paura a mettere il suo nome: NON scrivere il suo
  nome nel sito finché non decide dopo l'avvocato.
- Dati salvati oggi: report completi + email (store webhook-reports) e
  indice My Reports (user-reports) senza scadenza. Proposta in attesa:
  cancellazione automatica dopo 30 giorni e rimozione di My Reports
  ("strada A"), oppure report solo a schermo senza email ("strada B").
- Già fatto: IP mai più salvati in chiaro (HMAC) e contatori scaduti
  cancellati da soli (rateLimit.js).
- Da valutare con l'avvocato: AI Act art. 50(2) (marcatura leggibile a
  macchina dei testi AI), domicilio ex D.Lgs. 70/2003 art. 7.

## Motore dei report con fonti (pubblicato il 2026-10-22, main 0bac6ce)

Nato da un fact-check del 2026-10-21: nelle anteprime del vecchio motore
(Haiku 4.5, tutto a memoria) solo il 23% dei 111 fatti controllabili era
corretto (festival con scadenze passate, enti inventati, FAAN = aeroporti
nigeriani proposto come fondo). Con il nuovo motore, sulla copia di prova:
anteprime 88% corrette, 0 inventati; report completi 64% corretti, 0 inventati.
- Modello `claude-haiku-5-5` (anteprima effort `low`). `anthropic.js`
  `callClaude`: legge i blocchi per tipo (thinking prima), gestisce
  `pause_turn` e `refusal`, raccoglie gli URL restituiti dalla ricerca.
- Ricerca web Anthropic (`web_search_20250305`): anteprima 2 ricerche (un film
  di confronto, un festival), report completo fino a 22 (sezioni B, C, D, E
  in `reportPrompts.js`). Costo misurato: anteprima ~0,025 $, report
  completo ~0,22-0,24 $ (3/4 sono le ricerche, 10 $ ogni 1000).
- `grounding.js`: un fondo/festival/film/agente/piattaforma resta SOLO se il
  suo `source_url` è tra gli URL della ricerca di quella richiesta; date e
  cifre restano solo se i numeri sono sulla pagina scaricata; nei testi si
  tolgono le frasi con importi o date non presenti nelle pagine; niente cifre
  da siti aggregatori (lista `AGGREGATORS`); scadenze passate -> "Closed (...)";
  via i tag `<cite>`. Test in scratchpad `tests/` (si perdono a fine sessione).
- Punteggio: rubrica in `SCORING`; voto finale = media delle 5 aree (prima
  6 progetti diversissimi prendevano tutti 7.2-7.5).
- Niente previsioni di incasso in euro né prezzi E&O: "Revenue Scenarios" a
  parole (i report vecchi salvati mantengono il layout vecchio).
- Ogni voce mostra "Source: dominio · checked data" su sito, PDF e mail.
- Fact-check finale sul sito live (2026-10-22): anteprime 90% corrette,
  report completi 78% corretti, 0 enti inventati (vecchio motore: 23%).
- `verifiedFacts.js`: fatti verificati A MANO sulla fonte primaria, per quando
  le pagine trovate sono vecchie. Oggi: tax credit italiano 30% per produttori
  indipendenti (film e corti), tetto 4 mln per opera, D.I. MiC-MEF 6 luglio
  2026 n. 281 (la pagina riassuntiva DGCA mostrava ancora 25-40%). Va
  ricontrollato quando cambia la legge. Viene messo nel prompt e sovrascrive
  `tax_incentive` per i progetti italiani.
- Problemi noti ancora aperti (fact-check 2026-10-22): regole di prima
  visione a volte parafrasate male, fondi chiusi o non accessibili senza
  scadenza scritta, alcuni film di confronto poco pertinenti.
- Per testare: PR bozza #81 (`test-sourced-reports`) -> deploy preview
  `deploy-preview-81--oneciak.netlify.app`; `start-full-report` lancia la
  generazione sulla preview stessa. Mail di prova a `delivered+X@resend.dev`
  (non arrivano a nessuno). Limite: 3 report completi ogni 3 ore per IP,
  condiviso con il sito live (stesso store).

## Percorso del film e regole citate alla lettera (2026-10-24)

- **`/roadmap/`** ("Film roadmap"): 9 fasi (idea e sceneggiatura, diritti e
  società, budget, finanziamento, preparazione, riprese, post, festival,
  vendita e uscita), 49 lavori con spunta (salvate solo nel browser,
  `oneciak-roadmap-v1`), 27 citazioni ciascuna verificata parola per parola
  sulla fonte il 2026-10-24 (script `verify_page.js` in scratchpad
  `roadmap/`, si perde). Stili in `guides/guides.css` (sezione roadmap).
  Collegata da: barra in alto della home, menu, footer, guide, sitemap, e dal
  report (`roadmapBlock()`: riga "Your stage" sotto i 5 voti, mappa
  `STAGE_TO_ROADMAP` fase del modulo -> fase 1-9). Se cambia una regola
  citata, ricontrollare la fonte e la data.
- **Regole alla lettera nel report**: campo `rule_quote` per fondi, festival,
  lab (e festival dell'anteprima). `grounding.js` `checkQuote`/`quoteOnPage`:
  resta solo se la frase è sulla pagina della fonte identica (ignora
  maiuscole, spazi, virgolette curve, trattini, entità HTML); mai da siti
  aggregatori; i PDF non si leggono, quindi le citazioni da PDF cadono. Prova
  del 2026-10-24 su 7 report veri: 21 citazioni tenute, tutte e 21 ritrovate
  identiche sulla pagina con un controllo separato (`allq.js` in scratchpad).
- Film di confronto: campo `match` ("In common: ...") e regola: fuori se le
  fonti non confermano formato e genere.
- Scadenza mancante: "Not published on the source, check before planning".
- PDF in Carlito: `fonts/carlito-400-pdf.ttf` e `-700-pdf.ttf` (sottoinsieme
  latino fatto con pyftsubset, nomi/licenza OFL conservati), caricati solo al
  clic (`newPdfDoc()`), Helvetica se il font non carica.
- Niente trattini lunghi nel testo visibile (UI, PDF, mail, oggetto mail).
  Restano in privacy/termini: si riscrivono dopo l'avvocato.
- `generateFullReport.js`: pausa 6 s / 12 s tra i tentativi dopo un errore
  dell'API (prima riprovava subito). Il 2026-10-24 2 report su 3 lanciati
  insieme sono falliti senza motivo registrato; rilanciati, sono andati.
- Debug solo per la preview: il ramo `test-sourced-reports` (PR #81) ha in
  più un commit "TEST ONLY" (motivo dell'errore in get-report e limite 12
  report con `CONTEXT=deploy-preview`). MAI portarlo su main.

## Report su iPhone (2026-10-24, PUBBLICATO il 2026-10-26, main e98d964)

Antonio: "il full report da iPhone è troppo pesante da leggere e pieno di
finestre a destra e a sinistra, l'esperienza deve essere unica e piacevole".
Fatto SOLO sul branch e sulla preview (`deploy-preview-81`), commit 92f75f0
e 6e1d632, NON su main. Pubblicare solo quando Antonio dice "pubblica"
(procedura solita, cherry-pick di quei due commit, MAI il commit "TEST ONLY").
- Voto subito sotto il titolo; riassunto hero tagliato a 4 righe con
  "Read more" (`setHeroSummary`, solo telefono).
- `parasFold()`: prima frase visibile, il resto sotto "Read the full
  analysis" / "Read the full summary" (`details.more`).
- Ordine di ogni area: giudizio, una frase, "What to do", rischi/punti di
  forza (pallino colorato invece della riga verticale), poi tendine (anche
  "Next 90 days"). Fasi del piano d'azione: prima frase + "More".
- Pulsante "Next" in fondo a ogni area (`nextArea()`): chiude e apre la
  successiva. Su telefono l'intestazione sparisce scorrendo in giù
  (`body.rh-hidden`), resta solo la barra delle aree.
- Misure (Chromium come iPhone 13, NON Safari vero): voto da 678 a 184 px
  dall'alto; "What to do" da 1.184-1.806 a 340-477 px dal titolo dell'area;
  report tutto aperto da 17.676 a 13.505 px.
- Dubbio aperto: non è certo cosa intendesse con "finestre a destra e a
  sinistra". Gli è stato chiesto uno screenshot dal suo iPhone.

## Stato al 2026-10-26 e cosa manca

Online su oneciak.com (vedi sezioni sopra per il 2026-10-26): motore report con fonti, regole citate
alla lettera, percorso del film `/roadmap/`, guide, Carlito ovunque (PDF
compreso), niente etichette sopra i titoli, niente trattini lunghi.
Da fare, in ordine:
1. Fatto il 2026-10-26: report iPhone, giro Impeccable, chiaro/scuro.
2. Eventuali altri giri Impeccable 4.7.0 per migliorare ancora il sito
   (`/impeccable critique`, `audit`, `polish`, `layout`, `typeset`, `adapt`
   per i telefoni). Il controllo automatico gira già dopo ogni modifica (hook
   in `.claude/settings.local.json`, committato). Regole: mostrare prima e
   dopo con misure, aspettare l'ok per i cambi visivi grossi, non riaprire
   satinato/grana, palette e font già scelti.
3. Avvocato: privacy (titolare, basi giuridiche, trasferimenti USA, tempi di
   conservazione), strada A o B, nome di Antonio sul sito. Dopo: riscrivere
   privacy/termini (lì restano trattini lunghi).
4. Lancio (Product Hunt, Reddit, scuole): dopo l'avvocato; serve la frase di
   Antonio sul "perché" e una data. Ogni testo lo approva lui.
5. Report: nei corti spesso nessun film di confronto (regola severa, voluto);
   le regole dentro PDF non vengono citate (non si leggono i PDF).
6. PR #81 resta bozza di prova: non va mai mergiata.

## Giro Impeccable del 2026-10-26 (pubblicato)

Critica 26/40 (`.impeccable/critique/`). Fatto: le 5 aree non si ripetono più
(domande dentro la scheda della home, nel report una sola lista con barra in
ogni riga, niente `areaOverview`), niente etichette mono maiuscole come
etichette (restano solo su numeri, date, conteggi: le etichette sono parole in
Carlito grassetto), rischio/opportunità come inizio di frase, errori nella
pagina invece di `alert()` (`unlockFail`, `pdfFail`), caricamento allineato a
sinistra con il titolo del film, bottone sempre "Analyze your film", icone
disegnate (chevron, spunta) invece dei simboli ▾ ✓, "How to read" e glossario
sotto le aree, l'anteprima non ripete più il riassunto due volte.

## CHIARO E SCURO (deciso da Antonio il 2026-10-26, pubblicato)

Il sito segue l'impostazione del dispositivo (`prefers-color-scheme`), niente
pulsante, niente orario. Blocchi CSS in fondo agli stili di index.html
("LIGHT AND DARK") e in fondo a `guides/guides.css`; anche privacy, termini,
404.
- **Chiaro**: BIANCO VERO `#ffffff` ovunque, home compresa ("quando è bianco
  deve essere bianco, non quel grigino"): niente satinato, niente grana, niente
  crema. Bagliori leggeri solo ai bordi: pesca/rosso in alto a destra, azzurro
  `rgba(88,146,196,…)` a sinistra (il petrolio su bianco sembrava una macchia
  grigia sporca). Scheda Northbound in vetro chiaro.
- **Scuro**: nero prugna ovunque, anche analisi, modulo, My Reports, guide,
  roadmap; bagliori blu/rosso fissi ai bordi (`body::before`), grana overlay.
  Antonio: "il blu/rosso con sfondo nero è bellissimo".
- Senza preferenza vale il vecchio stile (hero scuro, resto chiaro).
- Contrasto misurato sui pixel in entrambe le modalità, 320-1440px, ogni
  schermata: tutto sopra soglia. 140 stati controllati: nessun errore JS,
  nessuno scorrimento orizzontale. Verifica in Chromium, NON Safari vero.
- Il satinato/grana delle parti chiare descritto sopra NON si usa più in
  modalità chiara (resta solo come stile senza preferenza).

## Principio di onestà (esplicito, non derogabile)

Mai inventare o gonfiare numeri/statistiche mostrate agli utenti (es. il
contatore "report generati" è stato tolto dalla home invece di falsificarlo
quando era troppo basso per sembrare affidabile). Stesso principio per i link:
verificarli sempre prima di presentarli come funzionanti (vedi
`netlify/functions/_util/linkCheck.js` per i report reali, verifica manuale
per il report di esempio statico).
