# OneCiak: il motore dei report

<!-- Letto solo quando serve: il puntatore sta in CLAUDE.md. -->
Modello, controlli sulle fonti, idoneità, scrittura, voti, qualità misurata
e come provarlo sulla preview #81.

## Modello e costi

- `claude-haiku-5-5` con ricerca web. Anteprima (`analyze.js`, effort
  `low`): 2 ricerche, ~0,025 $. Report completo (`reportPrompts.js`,
  sezioni A-G, ricerche B 6, C 5, D 6, E 5, G 5, `FULL_MAX_TOKENS` 32000:
  meno tronca il JSON): ~0,35-0,40 $, per tre quarti ricerca web.
- `_util/project.js` (`sanitizeProject`) tiene solo i campi noti; paese e
  lingua con la maiuscola (`properName`, uguale nella pagina).

## Controlli sulle fonti (`grounding.js`)

- Una voce resta solo se la sua fonte è tra i risultati della ricerca; date
  e cifre solo se sono sulla pagina (quelle del progetto contano come
  verificate); `rule_quote` solo se è sulla pagina parola per parola (i PDF
  non si leggono); `applicant` solo con la sua `rule_quote`.
- **Produttori**: restano solo se una pagina della ricerca nomina azienda e
  film insieme (`checkNamed`, `findNamingPage` su al massimo 25 pagine).
  L'email non nomina mai un'azienda ([COMPANY NAME]). Come accettano
  progetti (`checkApproach`): solo la loro frase parola per parola, dalla
  pagina `approach_url` sul loro sito (`ownSite`); altrimenti "not found on
  their site. Ask before you send a script.". In cima al passo la regola
  di Film4 ("we cannot consider unsolicited material", channel4.com).
- **Film di confronto** (`checkComp`): solo se la pagina dice il genere (e
  "short" per un corto); anno e budget solo se sulla pagina. **Agenti e
  piattaforme** (`checkListed`): solo se la pagina contiene il nome.
- **Scadenze** (`closingDateIn`, dopo "until", "deadline", "by", "entro"):
  passata "Closed (...)", assente "Not published on the source, check
  before planning".
- **Fondi da fonti deboli**: da un aggregatore (`AGGREGATORS`) restano solo
  i nomi, senza scadenze, cifre e citazioni; un fondo trovato solo lì, su un
  sito di notizie (`NEWS`) o detto preso da un "third-party site"
  (`THIRD_PARTY`) viene tolto, con le righe di "Before you can apply" che lo
  nominano (`dropStepsForGoneFunds`). Una lista non sarà mai completa: una
  lista di siti ufficiali ammessi sarebbe più sicura.
- **Link**: dopo `linkCheck`, `dropDeadSources` toglie intera ogni voce con
  la fonte morta. Una `rule_quote` che comincia a metà elenco (`FRAGMENT`)
  non regge "Who can apply".
- `verifiedFacts.js`, controllati a mano (ricontrollare se cambia la
  legge): tax credit italiano 30% per produttori indipendenti, tetto 4 mln
  (D.I. MiC-MEF 6/7/2026 n. 281); bando MiC selettivi 2026 (d.d. 15/5/2026
  n. 1238): scrittura per autori persone fisiche, opere oltre 52 min, in
  italiano, no IA; sviluppo e produzione solo imprese indipendenti italiane
  Ateco 59.1 con un'opera negli ultimi 5 anni. `applySelective` sistema
  queste righe.

## Chi può fare domanda (`eligibility.js`)

Fondi, festival e laboratori la cui frase (`rule_quote`, `eligibility`,
`fit`) esclude il progetto vengono tolti, anche nell'anteprima: paese
(`excludes`, ~50 paesi), formato, durata, lungometraggi già fatti, lavori
precedenti richiesti per "First film" (`excludesWork`). Solo frasi che
limitano chi entra; frasi con "not" non giudicate. Non controllati: fase
del progetto e società richiesta.

## Scrittura e voti

- `STYLE` (anche nell'anteprima) e `LENGTH`: un'idea per frase, ~20
  parole, "you", termini spiegati, mai "I"/"we"; ogni area 3-4 frasi,
  problemi e punti di forza 1-3, consigli 2-3, ogni punto in una sola area.
- Rubrica `SCORING` in tutte le chiamate: il voto giudica il progetto, mai
  la fase (copione non scritto, soldi non trovati, film non girato non
  abbassano il voto). Negli esempi JSON dei prompt nessun numero (un "6"
  lì faceva finire tutto tra 4,5 e 6). `_util/scores.js`: voti 1-10
  (`normalizeScores`), voto finale = media delle 5 aree
  (`overallFromAreas`). Lo stesso progetto può prendere voti diversi di
  qualche decimo tra un giro e l'altro.
- Nessun confronto con altri report, niente previsioni di incasso né prezzi
  E&O, nessuna frase-verdetto sotto il voto. Ogni voce: "Source: dominio ·
  checked data".

## Qualità misurata

23 novembre 2026, 5 report della preview (corto italiano, lungo USA, primo
film francese, film britannico girato, film croato finanziato): 86 voci, 68
giuste sulla fonte, 4 sbagliate, 14 non verificabili da qui; le 3 cause
corrette il 24 novembre. Problemi noti: a volte nessun produttore
verificato; regole di prima visione a volte parafrasate male; nei corti
spesso nessun film di confronto (voluto). Alcuni siti (Wix) a volte non
mostrano i film: ricontrollare più volte.

## Provare il motore (preview #81)

PR bozza #81 (`test-sourced-reports`), anteprima
`deploy-preview-81--oneciak.netlify.app`. Ha commit "TEST ONLY": mai su main
né mergiata. Per aggiornarla: checkout dei file del motore (e di
`index.html`) dal branch di lavoro sopra `origin/test-sourced-reports`, poi
`tests/engine.js` sulla preview. Mail di prova a `delivered+X@resend.dev`.
