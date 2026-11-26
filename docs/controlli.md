# OneCiak: i controlli nel dettaglio

<!-- Letto solo quando serve: il puntatore sta in CLAUDE.md. -->
Cosa provano i programmi in `tests/` e i controlli che restano a mano.

## Controlli (dopo ogni modifica visibile o pulizia)


Tutti partono insieme con `tests/check.sh` (e prima di ogni pubblicazione
con `tests/publish.sh`); `/tests/*` è chiuso con 404 in `netlify.toml`.
`tests/lint.js` legge il codice (simboli di testo, trattini lunghi,
pillole, `transition: all`, `scale(0)`, misure fuori scala, hover fuori da
`@media (hover: hover) and (pointer: fine)`); `tests/shots.js A B` fa il
foglio di foto prima e dopo di ogni vista, da guardare con gli occhi
(anche fondo del modulo, anteprima, prima pagina del PDF e mail: la mail
"prima" è `email.js` di `origin/main`; ogni foto aspetta la fine delle
animazioni). Gli
altri, anche da soli su un server locale o sul sito vero:
`NODE_PATH=/opt/node22/lib/node_modules node tests/functions.js [url]`
(161 prove su telefono e computer, compresa la colonna del report su
schermi bassi e il titolo con "Riduci movimento": menu, modulo, ogni area, ogni blocco,
ogni passo, ogni voce dell'indice, glossario, copia email, PDF,
calendario, roadmap, 404) e `node tests/pages.js [url]` (264 viste: ogni
pagina × 8 schermi, compresi 1366x657 e 1280x600 × 3 schemi; errori, richieste fallite, pagina larga,
testo azzurro, trattini lunghi, mezzi pixel; una richiesta fallita conta
solo se fallisce anche riprovandola due volte). Ogni giro di `check.sh` usa una
porta libera: due giri insieme sulla stessa porta si spegnevano il server. Se cambia una funzione, si
aggiorna il programma nello stesso commit. Terzo e quarto, `tests/rules.js`
(caratteri, `:active`, angoli 10px, maiuscolo, contrasto su ogni vista; in
locale la 404 è quella di python, in Times) e `tests/press.js` (stessa
pressione su ogni tasto). Quinto, `tests/motion.js A B`: confronta i movimenti di
ogni elemento tra due versioni (di solito il sito vero e il server locale)
e segnala quelli cambiati e, soprattutto, quelli PERSI (una cosa che si
muoveva e ora salta): va lanciato prima di ogni pubblicazione che tocca il
CSS. Nato dal 24 novembre 2026: il blocco ONE PRESS aveva tolto lo
scivolamento alla colonna del report e la sfumatura dell'ombra ai 4
bottoni principali, e nessun controllo se n'era accorto.

Sesto, solo a mano e solo quando cambia il motore: `node tests/engine.js
https://deploy-preview-81--oneciak.netlify.app/` (dopo aver aggiornato la
preview, vedi `docs/motore.md`). Compila il modulo come un visitatore, chiede
un'anteprima vera al motore (circa 0,025 $, 20 secondi) e controlla: 5 voti da
1 a 10 con i testi, voto finale uguale alla media, film e festival solo con
fonte controllata, niente errori a schermo né trattini lunghi. La risposta
intera va in `$OUT/engine.json`. Sul sito vero si rifiuta di partire.

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
