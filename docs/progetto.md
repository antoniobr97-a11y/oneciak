# OneCiak: ricerca, sicurezza, legale, marketing, strumenti

<!-- Letto solo quando serve: il puntatore sta in CLAUDE.md. -->

## Ricerca


- Doc privato "Come si fa davvero un film" (claude.ai/artifact/JrLNDdn3koDmXdo6Lv3MuH):
  solo il 25,3% degli esordienti fa un secondo film entro 5 anni (Stephen
  Follows, 19 agosto 2026); in Italia senza società di produzione niente
  fondi per sviluppo e produzione; "Your first film will probably be
  funded" (Follows, 28 ottobre 2026). Da qui "Before you can apply", "Make
  a short first", produttori e scadenze.
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
  Fa: controllo a fondo del sito vero (`tests/check.sh` e `docs/controlli.md`, con foto),
  correzione e prova degli errori secondo la regola 5 (online quando
  Antonio scrive "pubblica"), "punto della situazione"
  (sito in breve, cosa è cambiato dal git log di main, 3 cose da "Cosa
  manca") e 3 post come Artifact privato (bozze: li pubblica Antonio).
  Il primo lunedì del mese cerca anche skill nuove (Antonio, 25 novembre
  2026: trovarle da soli, "robe serie", non da TikTok): al massimo 3, solo se
  risolvono un problema che abbiamo avuto, autore riconoscibile, licenza MIT
  o Apache, aggiornate da meno di 3 mesi, lette tutte e provate su un caso
  nostro fuori dal repo; si installano solo col sì di Antonio.
  Se cambiano i controlli, aggiornare anche il suo testo.
- r/Screenwriting vieta contenuti AI, r/Filmmakers vieta i post solo-link.

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
- **Retro** e **writing-for-agents** (`.claude/skills/`, da github.com/
  mattpocock/skills commit d653911, MIT; solo testo, retro parte solo se
  chiamata): `/retro` a fine lavoro, cerca cosa cambiare perché gli errori
  non si ripetano (controlli automatici prima di regole scritte).
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
