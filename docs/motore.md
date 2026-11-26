# OneCiak: il motore dei report

<!-- Letto solo quando serve: il puntatore sta in CLAUDE.md. -->
Modello, controlli sulle fonti (grounding), idoneità, scrittura, voti,
qualità misurata e come provarlo sulla preview #81.

## Motore dei report


- Modello `claude-haiku-5-5` (anteprima effort `low`) con ricerca web:
  anteprima 2 ricerche; report completo sezioni A-G di `reportPrompts.js`
  (ricerche B 6, C 5, D 6, E 5, G 5), `FULL_MAX_TOKENS` 32000 (meno tronca
  il JSON). Costo misurato: anteprima ~0,025 $, report completo ~0,35-0,40 $
  (la ricerca web è circa tre quarti). Credito prepagato il 9 novembre
  2026: 22,02 $, poi sceso con le prove. Limite di spesa Anthropic: 50 al
  mese.
- `grounding.js`: una voce resta solo se la sua fonte è tra i risultati
  della ricerca; date e cifre solo se sono sulla pagina (quelle del
  progetto contano come verificate); niente cifre da aggregatori; scadenze
  passate "Closed (...)"; `rule_quote` solo se è sulla pagina parola per
  parola (i PDF non si leggono); `applicant` solo con la sua `rule_quote`.
- **Produttori**: restano solo se una pagina della ricerca nomina azienda
  (senza Srl/Ltd...) e film insieme (`checkNamed`, `findNamingPage` su al
  massimo 25 pagine); un "film" uguale al nome dell'azienda è scartato.
  L'email non nomina mai un'azienda ([COMPANY NAME]). Come accettano
  progetti (`checkApproach`): solo la loro frase parola per parola, dalla
  pagina `approach_url` sul sito dell'azienda (`ownSite`: l'indirizzo
  contiene una parola distintiva del nome), escluse pagine di distribuzione
  e frasi tagliate a "contact:". Sul sito: "How they take projects, word
  for word" col link, altrimenti "not found on their site. Ask before you
  send a script." (una volta sola se nessuna ce l'ha). In cima al passo la
  regola di Film4 ("we cannot consider unsolicited material", channel4.com,
  controllata l'11 novembre 2026).
- **Chi può fare domanda** (`eligibility.js`): fondi, festival e laboratori
  la cui frase (`rule_quote`, `eligibility`, `fit`) esclude il progetto
  vengono tolti, anche nell'anteprima: paese (`excludes`, tabella di ~50
  paesi), formato, durata, lungometraggi già fatti e, per "First film",
  lavori precedenti richiesti (`excludesWork`). Solo frasi che limitano chi
  entra, non prima visione, soldi o lingua; frasi con "not" non giudicate.
  62 frasi di prova tutte giuste (12 novembre 2026). Sul sito "Who can
  apply" solo con la frase della fonte.
- **Film di confronto** (`checkComp`): solo se la pagina dice il genere (e
  "short" per un corto); anno e budget solo se sulla pagina. **Agenti e
  piattaforme** (`checkListed`): solo se la pagina contiene il nome.
- **Scadenze** (`closingDateIn`): conta la data dopo "until", "deadline",
  "by", "entro". Anche laboratori e mercati: passata "Closed (...)",
  assente "Not published on the source, check before planning". Aggregatori (`AGGREGATORS`): il nome resta, scadenze,
  cifre e citazioni no; un fondo trovato solo su un aggregatore viene tolto
  e con lui le righe di "Before you can apply" che lo nominano
  (`dropStepsForGoneFunds`, che toglie anche quelle dei fondi scartati da
  altri controlli). Un fondo va via anche se viene da un sito di notizie
  (`NEWS`: variety, screendaily, cineuropa...) o se il report stesso lo
  dice preso da un "third-party site" (`THIRD_PARTY`). Dopo `linkCheck`,
  `dropDeadSources` toglie intera ogni voce con il link della fonte morto
  (prima restava la riga "Source" col link rotto). Una `rule_quote` che
  comincia a metà elenco ("soit par...", "or by...", `FRAGMENT`) non regge
  "Who can apply" e sparisce (il CNC diceva "solo società" ma accetta anche
  il regista). xhbt.org (da dove arrivò un fondo di Milano proposto a
  un progetto del Kansas) blocca i programmi: non verificato se è un
  aggregatore, non è in lista.
- `verifiedFacts.js`, fatti controllati a mano (ricontrollare se cambia la
  legge): tax credit italiano 30% per produttori indipendenti, tetto 4 mln
  (D.I. MiC-MEF 6/7/2026 n. 281); bando MiC selettivi 2026 (d.d. 15/5/2026
  n. 1238): scrittura per autori persone fisiche, opere oltre 52 min, in
  italiano, no IA; sviluppo e produzione solo imprese indipendenti
  italiane Ateco 59.1 con un'opera negli ultimi 5 anni (salvo società
  nuove). `applySelective` sistema queste righe.
- **Scrittura** (`STYLE`, anche nell'anteprima; `LENGTH` nel `PREAMBLE`):
  un'idea per frase, ~20 parole, "you", termini spiegati, mai "I"/"we";
  ogni area 3-4 frasi, problemi e punti di forza 1-3, consigli 2-3, ogni
  punto in una sola area. `stageRules`; rubrica `SCORING` (in tutte le
  chiamate, anche dell'anteprima): il voto giudica il progetto, mai la fase
  (copione non scritto, soldi non trovati, film non girato non abbassano il
  voto), con esempi area per area e tutta la scala; negli esempi JSON dei
  prompt nessun numero (un "6" lì faceva finire tutto tra 4,5 e 6).
  `_util/scores.js`: voti in numeri 1-10 (`normalizeScores`) e voto finale =
  media delle 5 aree (`overallFromAreas`). Il modello non scrive più `overall_label` (la frase di 3-5 parole sotto il voto): tolta dai prompt il 25 novembre 2026. Misurato il 16 novembre 2026 su 6
  progetti diversi (2 giri ciascuno): prima 3,6-5,6, dopo 2,0-6,5, stabile
  entro 0,2. Nessun confronto con altri report ("più alto del 28% di 18
  progetti": erano quasi tutte prove, tolto). Niente previsioni di incasso
  né prezzi E&O. Ogni voce:
  "Source: dominio · checked data".
- **Qualità** (23 novembre 2026, 5 report nuovi della preview: corto
  italiano, lungo USA, primo film francese, film britannico girato, film
  croato finanziato): 86 voci, 68 giuste sulla fonte, 4 sbagliate (2 link
  morti, 1 fondo da un sito di elenchi, 1 "Who can apply" sbagliato), 14
  non verificabili da qui; le 3 cause corrette il 24 novembre (vedi sopra),
  poi 2 report di prova senza nessuno dei 3 errori. Nei 7 report 5 fondi su
  19 venivano da siti non ufficiali (creativepathwayscanada.com, variety.com,
  dossierdeprod.fr due volte, les-aides.fr): aggiunti alle liste, ma una
  lista non sarà mai completa. Prima misura (11 novembre 2026, 3 report: corto italiano,
  lungometraggio francese, lungometraggio USA): 57 voci con fonte, 46
  giuste, 0 sbagliate, 11 non verificabili da qui. Ogni giro dà voci
  diverse; alcuni siti (Wix) a volte non mostrano i film: ricontrollare
  più volte. Problemi noti: idoneità non controllata su fase e società
  richiesta; a volte nessun produttore verificato; regole di prima visione
  a volte parafrasate male; nei corti spesso nessun film di confronto
  (voluto).
- **Prove**: PR bozza #81 (`test-sourced-reports`), anteprima
  `deploy-preview-81--oneciak.netlify.app`, genera i report sulla preview.
  Ha commit "TEST ONLY": MAI su main né mergiata. Per aggiornarla: checkout
  dei file del motore dal branch di lavoro sopra
  `origin/test-sourced-reports`, poi `tests/engine.js` sulla preview
  (`docs/controlli.md`). Mail di prova a `delivered+X@resend.dev`.
