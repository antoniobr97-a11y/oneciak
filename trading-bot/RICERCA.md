# Cosa dice la letteratura, e cosa manca a questo bot

Analisi di quello che la ricerca accademica e la pratica professionale
hanno stabilito sui sistemi come questo, e di quali idee sono davvero
applicabili qui.

**Che cos'è questo bot, in una riga:** un sistema *long-only*, su
timeframe giornaliero, che segue i trend entrando sui ritracciamenti,
con filtro di regime di mercato, size a frazione fissa del rischio e
uscita a scaglioni. Più un portafoglio statico di ETF a fianco.

Questa descrizione conta, perché delimita quali risultati della
letteratura lo riguardano e quali no.

---

## Parte 1 — Quello che il bot già fa, e che la ricerca conferma

Vale la pena dirlo prima, perché è la parte solida.

| Cosa fa il bot | Cosa dice la ricerca |
|---|---|
| **Filtro di regime** (opera solo se l'indice è sopra la SMA200) | Faber (2007), *A Quantitative Approach to Tactical Asset Allocation*: la regola della media a 10 mesi riduce drawdown e volatilità su ogni classe di attivo testata, su un secolo di dati. È esattamente questo meccanismo |
| **Priorità ai titoli vicini al massimo a 52 settimane** | George & Hwang (2004), *The 52-Week High and Momentum Investing*: la vicinanza al massimo annuale predice i rendimenti **meglio** del momentum classico. Già citato nel codice |
| **Solo long, mai short** | Coerente con la misura fatta qui (gli short perdono in ogni versione) e con la letteratura: il momentum short costa di più in commissioni/prestito e crolla nei rimbalzi |
| **Size proporzionale al rischio per azione** | È volatility scaling a livello di singola posizione: un titolo volatile ha stop più largo, quindi meno azioni. Standard nella gestione sistematica |
| **Lasciar correre i vincitori** | Il risultato più consolidato sul trend following: il profitto viene da pochi grandi vincitori. Il test fuori campione fatto qui (2R contro 3R) lo ha confermato: incassare prima **peggiora** |
| **Diversificazione fra strategie scorrelate** | Correlazione misurata 0,28 fra le due metà. Il mix batte entrambe da sole. È l'unico "pasto gratis" riconosciuto in finanza |

Non è poco. La struttura portante è allineata a ciò che funziona.

---

## Parte 2 — Le tre idee che valgono davvero, in ordine di forza

### 2.1 Ridurre l'esposizione quando il mercato è volatile ⭐ la più importante

**Cosa dice la ricerca.** È il risultato più forte degli ultimi vent'anni
sul momentum, e riguarda esattamente il problema che qui interessa di più.

Barroso & Santa-Clara (2015), *Momentum Has Its Moments*: il momentum ha
crolli rari e devastanti, e **quasi tutti arrivano quando la volatilità è
già alta**. Scalando le posizioni in modo inverso alla volatilità recente,
lo Sharpe raddoppia circa e la coda negativa si accorcia drasticamente.

Daniel & Moskowitz (2016), *Momentum Crashes*: stessa diagnosi. I crolli
si concentrano in periodi di alta volatilità che seguono grandi ribassi —
sono prevedibili **nel rischio**, anche se non nella direzione.

Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum*: i gestori
professionali di trend following usano tutti una qualche forma di
*volatility targeting*. Non è una finezza, è prassi.

**Cosa fa il bot oggi.** Scala la size sulla volatilità del *singolo
titolo* (stop più largo → meno azioni). **Non scala l'esposizione
complessiva sulla volatilità del mercato.** Quando l'indice inizia a
sbandare, il bot tiene comunque fino a 12 posizioni all'1% ciascuna.

**Come si farebbe.** Misurare la volatilità recente dell'indice (es. 20
giorni) contro la sua media di lungo periodo, e ridurre il rischio per
operazione in proporzione: mercato calmo → 1% pieno; volatilità doppia del
normale → 0,5%. Nessun dato nuovo: serve solo SPY, che il bot già scarica.

**Perché è la prima della lista.** È l'unica idea che (a) ha il supporto
empirico più forte, (b) è realizzabile con i dati già disponibili, e (c)
punta dritta al drawdown, che è la cosa che interessa di più a chi usa
questo bot.

**ESITO (13 settembre 2026): MISURATA E RESPINTA.**

Fatta. In campione funzionava benissimo (drawdown da −17,5% a −12,4%).
Fuori campione il drawdown **peggiora** di 3,1 punti — e il criterio
scritto prima della misura chiedeva che migliorasse su entrambi gli
universi. Non entra.

Il dettaglio interessante: fuori campione rendimento e Sharpe migliorano
entrambi, e nelle crisi vere (2020, 2022) il freno protegge esattamente
come la letteratura promette. Tutto il peggioramento viene da un solo
episodio, il 2015-2016. Tabelle e ragionamento completo in STRATEGY.md,
"Freno di volatilità di mercato: misurato, respinto".

---

### 2.2 Ordinare i candidati con il momentum a 12-1 mesi

**Cosa dice la ricerca.** Jegadeesh & Titman (1993) è il lavoro fondativo:
comprare i titoli che hanno reso di più negli ultimi 3-12 mesi e vendere i
peggiori produce un extra-rendimento che è stato replicato su quasi ogni
mercato e ogni epoca. La versione canonica è **12-1**: rendimento degli
ultimi 12 mesi **escluso l'ultimo**, perché nel brevissimo c'è un effetto
di inversione che sporca il segnale.

Asness, Moskowitz & Pedersen (2013), *Value and Momentum Everywhere*:
funziona su azioni, obbligazioni, valute, materie prime, otto mercati.

**Cosa fa il bot oggi.** Ordina per vicinanza al massimo a 52 settimane —
che è un cugino stretto del momentum e ha il suo supporto (George & Hwang),
ma non è la stessa cosa. Sono due misure correlate ma distinte.

**Come si farebbe.** Aggiungere il momentum 12-1 come criterio di
ordinamento, da solo o combinato con la vicinanza al massimo. Dati già
disponibili.

**Nota onesta.** Qui il guadagno atteso è minore che al punto 2.1: il bot
usa già un segnale della stessa famiglia. È un affinamento, non una
mancanza.

### 2.3 Stop che sale dietro al prezzo sulla quota residua

**Cosa dice la pratica.** Meno accademia, più mestiere: i gestori di trend
following (Clenow, *Following the Trend*; Kaminski & Greyserman, *Trend
Following with Managed Futures*) usano quasi tutti uno stop che trascina,
non un livello fisso.

**Cosa fa il bot oggi.** Dopo il secondo obiettivo, il 20% residuo ha lo
stop fermo al pareggio e esce solo quando il prezzo rompe la SMA200. La
SMA200 è **lenta**: un titolo che sale a +8R e poi ritorna restituisce
tutto fino al pareggio prima che l'uscita scatti.

**Stato:** provato quattro volte, mai arrivato in fondo per i riavvii del
container di questo ambiente. Resta l'unica idea promessa e non
consegnata.

---

## Parte 3 — Idee forti nella letteratura, ma NON applicabili qui

Vale la pena elencarle, perché sapere perché una cosa non si può fare
evita di riproporla ogni mese.

| Idea | Perché non si applica |
|---|---|
| **Value + momentum insieme** (Asness et al.) — la combinazione più robusta che esista | Servono dati di bilancio (P/B, P/E, redditività). Il bot scarica solo prezzi. Si potrebbe fare, ma è un'altra fonte dati, un'altra infrastruttura, altri modi di sbagliare |
| **Post-Earnings Announcement Drift** (Bernard & Thomas, 1989): comprare dopo sorprese positive sugli utili funziona da 40 anni | Servono le stime degli analisti e l'utile effettivo. Ironia: il bot fa l'**opposto**, evita le trimestrali. Nessuna delle due scelte è sbagliata — sono strategie diverse |
| **Quality / profittabilità** (Novy-Marx) | Dati di bilancio |
| **Short interest, flussi istituzionali** | Dati a pagamento |
| **Intraday / microstruttura** | Il bot lavora su barre giornaliere e decide a mercato chiuso. Cambiare timeframe sarebbe un bot diverso |
| **Stagionalità ("sell in May")** | Debole, contestata, e molto sfruttata: candidata classica al sovradattamento |

---

## Parte 4 — Il punto scomodo: quanto valgono davvero queste idee

Qui serve onestà, perché è la parte che di solito manca.

**1. Il tasso di successo delle "buone idee" è basso.**
In questa stessa sessione: i filtri di rischio come veti hanno azzerato il
rendimento; il secondo obiettivo a 2R sembrava migliorare tutto e fuori
campione ha invertito il segno. **Due idee ragionevoli su due, bocciate
dai dati.** Un terzo è stato adottato (il limite per settore) perché ha
retto su due universi. Uno su tre è già un buon tasso.

**2. La letteratura soffre degli stessi mali.**
Hou, Xue & Zhang (2020) hanno ri-testato 452 anomalie pubblicate: la
maggioranza non si replica. McLean & Pontiff (2016) hanno misurato che un
effetto rende circa il **32% in meno** dopo la pubblicazione, e il 58% in
meno fuori campione. Anche le idee di questa pagina vanno prese con quel
fattore di sconto.

**3. Il momentum e il volatility targeting sono fra i pochi sopravvissuti.**
Sono stati replicati su decenni, mercati e classi di attivo diverse. Ecco
perché il punto 2.1 è in cima: non perché è nuovo, ma perché è vecchio e
non è ancora morto.

**4. E la cosa più importante non è in questa pagina.**
Il risultato di chi usa questo bot dipenderà, in ordine:

1. **da quanti soldi ci mette** — una perdita del 15% su 2.000 € e su
   50.000 € è la stessa percentuale e due esperienze diverse;
2. **dal mix 50/50** fra azioni ed ETF, già misurato e già corretto;
3. **dal restare fermi** quando il bot è in perdita — perché ci sarà, e
   sarà normale;
4. e **solo dopo**, da qualunque affinamento di questa pagina.

I punti 1-3 valgono più di tutto il resto messo insieme, e non richiedono
una riga di codice.

---

## Conclusione operativa

Una sola idea merita di essere messa alla prova adesso: **ridurre
l'esposizione quando la volatilità del mercato è alta** (2.1). Ha il
supporto empirico più forte, usa dati già disponibili, e attacca il
drawdown.

Sarà misurata come tutte le altre: ipotesi dichiarata prima, misura in
campione, e **conferma obbligatoria fuori campione** — dove il 2R è morto.
Se non regge lì, non entra nel bot.

Le altre due (momentum 12-1, stop trascinato) restano in lista, dopo.

### Riferimenti

- Jegadeesh & Titman (1993), *Returns to Buying Winners and Selling Losers*
- Bernard & Thomas (1989), *Post-Earnings-Announcement Drift*
- George & Hwang (2004), *The 52-Week High and Momentum Investing*
- Faber (2007), *A Quantitative Approach to Tactical Asset Allocation*
- Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum*
- Asness, Moskowitz & Pedersen (2013), *Value and Momentum Everywhere*
- Barroso & Santa-Clara (2015), *Momentum Has Its Moments*
- Daniel & Moskowitz (2016), *Momentum Crashes*
- McLean & Pontiff (2016), *Does Academic Research Destroy Stock Return Predictability?*
- Novy-Marx & Velikov (2016), *A Taxonomy of Anomalies and Their Trading Costs*
- Hou, Xue & Zhang (2020), *Replicating Anomalies*
