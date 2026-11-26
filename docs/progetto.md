# OneCiak: ricerca, sicurezza, legale, marketing, strumenti

<!-- Letto solo quando serve: il puntatore sta in CLAUDE.md. -->

## Ricerca

- Doc privato "Come si fa davvero un film"
  (claude.ai/artifact/JrLNDdn3koDmXdo6Lv3MuH): solo il 25,3% degli
  esordienti fa un secondo film entro 5 anni (Stephen Follows, 19 agosto
  2026); in Italia senza società di produzione niente fondi per sviluppo e
  produzione. Da qui "Before you can apply", "Make a short first",
  produttori e scadenze.
- Ricerca dell'11 novembre 2026: l'ostacolo principale è il produttore;
  molti produttori non leggono progetti non richiesti; nessuno fa gratis
  quello che fa OneCiak (controllato con WebSearch, non con Google); quante
  email a freddo funzionino va misurato con persone vere.

## Sicurezza

- `analyze.js` accetta solo `{project}`: i prompt si costruiscono sul
  server. `sanitizeProject` tiene solo i campi noti.
- `start-full-report` firma id+email+progetto (`payloadSig.js`); massimo 5
  report al giorno per email, 3 ogni 3 ore per IP, anteprime 10 l'ora per
  IP. IP mai salvati in chiaro (HMAC). Errori 500 generici al client.
  `admin-stats.html` manda la chiave in `X-Admin-Key`.
- Netlify pubblica tutta la cartella (`publish = "."`): ogni file non del
  sito (CLAUDE.md, docs, tests, funzioni, package*.json, `.claude/`,
  `.impeccable/`) va chiuso con 404 in `netlify.toml`.

## Legale (in sospeso: Antonio sente un avvocato)

Antonio non ha partita IVA. Privacy incompleta rispetto al GDPR art. 13
(titolare, basi giuridiche, trasferimenti USA, conservazione, reclamo al
Garante). Il nome di Antonio non va sul sito finché non decide. Oggi si
conservano senza scadenza report, email e l'indice My Reports; proposte:
cancellazione dopo 30 giorni e niente My Reports ("strada A") o report solo
a schermo ("strada B"). Da valutare: AI Act art. 50(2), D.Lgs. 70/2003 art.
7. Scheda per l'avvocato: claude.ai/artifact/Y776k28X7HyxzMxcQgNXDX. Il
testo legale del sito (casella e piè di pagina) lo rivede l'avvocato.

## Controllo del lunedì e marketing

- Controllo del lunedì (8:52 ora italiana, `trig_01Hw3VgdAYog52NywzNU8RK9`,
  nella sessione di lavoro principale): controllo a fondo del sito vero
  (`tests/check.sh` e `docs/controlli.md`, con foto), correzione e prova
  degli errori secondo la regola 5, punto della situazione, 3 post come
  Artifact privato (bozze: li pubblica Antonio). Il primo lunedì del mese
  anche skill nuove: al massimo 3, solo se risolvono un problema che
  abbiamo avuto, autore riconoscibile, licenza MIT o Apache, aggiornate da
  meno di 3 mesi, lette tutte e provate su un caso nostro fuori dal repo; si
  installano solo col sì di Antonio. Se cambiano i controlli, aggiornare
  anche il suo testo.
- Google indicizza già il sito (confermato da Antonio).
- r/Screenwriting vieta contenuti AI, r/Filmmakers vieta i post solo-link.

## Strumenti

- **Impeccable** (`.claude/skills/impeccable`): scanner di anti-pattern,
  `.claude/skills/impeccable/scripts/impeccable detect index.html`; falsi
  positivi spiegati in `.impeccable/config.json`.
- **Elephant-Goldfish Model** (plugin `egm@egm`, Apache 2.0, solo testo):
  prima di un cambiamento grosso il piano lo rileggono revisori senza
  memoria (`/egm:egm-review-loop` con `comprehension` e `design_critic`).
- **Retro** e **writing-for-agents** (`.claude/skills/`, da
  github.com/mattpocock/skills, MIT): `/retro` a fine lavoro per non
  ripetere gli errori (controlli automatici prima di regole scritte).
- **Emil Kowalski design-eng** (`.claude/skills/emil-design-eng`, MIT):
  regole per animazioni e tocco.
- **Prove nel browser**: Playwright con
  `NODE_PATH=/opt/node22/lib/node_modules`. Funzioni del server in locale:
  `@netlify/blobs` nello scratchpad e `NODE_PATH`.
- Scartati: Taste, awesome-claude-design, Context7, Graphify, 21st MCP,
  Agent Skills, Playwright CLI e MCP, il pacchetto ECC (286 skill). Strix
  rimandato (serve una chiave e un tetto di spesa decisi da Antonio).
