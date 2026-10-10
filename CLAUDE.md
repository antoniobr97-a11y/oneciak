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

## Principio di onestà (esplicito, non derogabile)

Mai inventare o gonfiare numeri/statistiche mostrate agli utenti (es. il
contatore "report generati" è stato tolto dalla home invece di falsificarlo
quando era troppo basso per sembrare affidabile). Stesso principio per i link:
verificarli sempre prima di presentarli come funzionanti (vedi
`netlify/functions/_util/linkCheck.js` per i report reali, verifica manuale
per il report di esempio statico).
