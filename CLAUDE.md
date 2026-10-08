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

Stato attuale di `:root` in `index.html` (già a posto, non toccare i valori
senza motivo):
- `--muted:#5c5c5c`, `--muted-light:#606060`, `--danger:#b13225` — scuriti
  apposta per restare sopra il minimo di contrasto WCAG AA (4.5:1) anche sopra
  il gradiente ambientale più intenso dell'hero. Se si schiarisce di nuovo lo
  sfondo o si intensifica il gradiente, **ricontrollare il contrasto**, non
  dare per scontato che vada bene.
- Bottoni: `border-radius: 10px` ovunque (non più `980px`/pillola piena —
  cambiato apposta, è uno dei tratti "AI generico" corretti).
- Sfondo ambientale: due macchie radiali (arancio `rgba(214,120,76,...)` +
  prugna `rgba(94,67,86,...)`) **asimmetriche** (una dominante, una piccola in
  un angolo) — non renderle di nuovo speculari/bilanciate.
- Hero della landing: testo **allineato a sinistra**, non centrato
  (`.l-hero-inner { align-items: flex-start; text-align: left }`).
- Hover con ombra/spostamento sono dentro
  `@media (hover: hover) and (pointer: fine)` — altrimenti restano "incollati"
  su mobile dopo un tap. Ogni elemento cliccabile ha un `:active` con
  `transform: scale(...)` per dare feedback al tocco.
- La schermata di caricamento (`#sec-loading`) mostra le 5 dimensioni
  (01-05, stessa numerazione di landing/risultati) che avanzano
  pending → active → done mentre si aspetta, invece di uno spinner generico.
  Guidato da `startLoadingDims([...secondi])` / `finishLoadingDims()` /
  `resetLoadingDims()` in JS — pacing plausibile basato sul tempo trascorso,
  non telemetria reale per-dimensione (le chiamate API non la espongono).

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

## Principio di onestà (esplicito, non derogabile)

Mai inventare o gonfiare numeri/statistiche mostrate agli utenti (es. il
contatore "report generati" è stato tolto dalla home invece di falsificarlo
quando era troppo basso per sembrare affidabile). Stesso principio per i link:
verificarli sempre prima di presentarli come funzionanti (vedi
`netlify/functions/_util/linkCheck.js` per i report reali, verifica manuale
per il report di esempio statico).
