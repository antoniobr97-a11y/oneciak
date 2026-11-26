# OneCiak: i controlli nel dettaglio

<!-- Letto solo quando serve: il puntatore sta in CLAUDE.md. -->
Cosa provano i programmi in `tests/` e i controlli che restano a mano.

## I programmi

`tests/check.sh` li lancia tutti su un server locale (porta libera a ogni
giro), `tests/publish.sh` li rifà prima di pubblicare e dopo riprova
`functions.js` e `pages.js` sul sito vero. `/tests/*` dà 404 sul sito. Se
cambia una funzione, il programma si aggiorna nello stesso commit; se un
errore sfugge ai programmi, si aggiunge la prova che l'avrebbe trovato.

- **`lint.js`** legge il codice: solo grigi (R=G=B, anche nel PDF), simboli
  di testo al posto delle icone, trattini lunghi, pillole, `transition:
  all`, `scale(0)`, misure fuori scala, hover fuori da `@media (hover:
  hover) and (pointer: fine)`.
- **Immagini** (in `check.sh`): nessun pixel colorato nelle immagini del
  sito (`og-image.png`, icone, `email-header.jpg`).
- **`functions.js [url]`**: ogni funzione su telefono e computer: menu,
  modulo, ogni area, blocco, passo e voce dell'indice, glossario, copia
  email, PDF, Report a problem, bottoni principali tutti uguali, colonna
  del report su schermi bassi e sopra il piè di pagina, titolo del
  caricamento su una riga, titolo con "Riduci movimento", paese e lingua
  con la maiuscola, roadmap, 404.
- **`pages.js [url]`**: ogni pagina × 8 schermi (compresi 1366x657 e
  1280x600) × 3 schemi: errori, richieste fallite (contano solo se falliscono
  anche riprovando due volte), pagina più larga dello schermo, testo
  azzurro, trattini lunghi, mezzi pixel.
- **`rules.js`**: caratteri, `:active`, angoli 10px, maiuscolo, contrasto
  su ogni vista (in locale la 404 è quella di python, in Times).
- **`press.js`**: stessa pressione su ogni tasto.
- **`motion.js A B`**: confronta i movimenti di ogni elemento tra due
  versioni (di solito sito vero e locale); un movimento PERSO (una cosa che
  si muoveva e ora salta) è un errore, uno CAMBIATO va guardato.
- **`shots.js A B`**: foto prima e dopo di ogni vista, da guardare con gli
  occhi (anche fondo del modulo, anteprima, PDF e mail; la mail "prima" è
  `email.js` di `origin/main`).
- **`engine.js <preview>`**, solo a mano e solo quando cambia il motore,
  sulla preview #81 aggiornata (`docs/motore.md`): compila il modulo come
  un visitatore, chiede un'anteprima vera (~0,025 $) e controlla voti,
  media, fonti, schermo. Sul sito vero si rifiuta di partire.

## Controlli a mano

- **Funzioni del motore**: un'analisi vera su `/.netlify/functions/analyze`
  (mai `start-full-report`, che manda una mail e costa).
- **Scaletta** che cambia col progetto: primo film, produttore presente,
  finanziato, corto.
- **Link esterni** di report di esempio e roadmap: 2xx/3xx. Locarno ha un
  controllo anti-robot (403): va aperto a mano.
- **Sicurezza da fuori** (solo letture): 404 per `/.git/HEAD`,
  `/.git/config`, `/package.json`, `/package-lock.json`, `/.npmrc`, `/.env`,
  `/CLAUDE.md`, `/docs/`, `/tests/`, `/netlify.toml`,
  `/.claude/settings.json`, `/.impeccable/config.json`,
  `/netlify/functions/*.js`; intestazioni HSTS, CSP, X-Frame-Options DENY,
  nosniff, Referrer-Policy, Permissions-Policy; http con 301 verso https;
  le funzioni con `Origin` estraneo rispondono solo `https://oneciak.com`;
  corpo sbagliato a `analyze` dà un errore corto. jsPDF 2.5.1 da cdnjs ha
  il sigillo `integrity`, uguale a quello di
  `api.cdnjs.com/libraries/jspdf/2.5.1?fields=sri`; se cambia versione,
  cambia anche il sigillo. `/admin-stats.html` risponde 200 apposta (serve
  la chiave).
- **Safari**: qui non c'è (Linux): serve l'iPhone di Antonio.

## Pubblicare a mano (se `tests/publish.sh` non si può usare)

```bash
git fetch origin main
git checkout -B main-fixN origin/main
git checkout <branch-di-lavoro> -- <file del sito>
git diff --cached origin/main --stat   # deve essere NON vuoto, altrimenti STOP
git commit && git push origin main-fixN:main
git checkout claude/website-completion-aesthetics-6wknns
```
Poi `mcp__github__get_commit` (righe aggiunte e tolte vere) e un ciclo su
`curl https://oneciak.com/?x=$i` finché il file servito è quello nuovo: la
CDN può servire la versione vecchia con 200.
