"""Central configuration, loaded from environment variables (.env).

Shared between the long_term/ and short_term/ strategies. See
../.env.example for every variable and its default.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _float(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val else default


def _int(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val else default


def _list(name: str, default: str) -> list[str]:
    return [s.strip().upper() for s in os.getenv(name, default).split(",") if s.strip()]


# --- Alpaca (paper trading broker) ---------------------------------------
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_PAPER = _bool("ALPACA_PAPER", True)

# Orario del ciclo giornaliero, fuso orario di mercato (America/New_York).
# DOPO la chiusura (16:00): la barra del giorno e' definitiva, come nel
# backtest e come nel corso ("si analizza la sera, si piazzano gli ordini").
# Gli ordini sono GTC e restano in coda fino alla riapertura, quindi non
# serve che il mercato sia aperto mentre il bot lavora.
RUN_TIME = os.getenv("RUN_TIME", "16:15")

# URL webhook opzionale (Telegram/Discord/Slack o endpoint generico che
# accetta {"text": "..."}) per notifiche di ordini eseguiti ed errori.
# Vuoto = notifiche disattivate (default), il bot funziona lo stesso.
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")

# File di stato per la gestione a scaglioni delle posizioni di breve
# termine (size originale, stadio 1R/3R raggiunto) -- vedi
# common/position_state.py. Va su un volume persistente in Docker.
POSITION_STATE_PATH = os.getenv("POSITION_STATE_PATH", "state/positions.json")


def require_alpaca_keys() -> None:
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        raise RuntimeError(
            "ALPACA_API_KEY / ALPACA_SECRET_KEY are not set. "
            "Copy .env.example to .env and fill in your paper trading keys."
        )


# --- Lungo termine (long_term/) -------------------------------------------
# Vedi STRATEGY.md Parte 1. ETF USA liquidi come default; sostituibili via env.
LONG_TERM_CAPITAL = _float("LONG_TERM_CAPITAL", 10_000.0)
LONG_TERM_RISK_SCORE = _int("LONG_TERM_RISK_SCORE", 25)  # punteggio questionario, vedi risk_profile.py

# Harry Browne: [azionario, obbligazionario_lungo, obbligazionario_breve, oro], 25% ciascuno
HARRY_BROWNE_TICKERS = _list("HARRY_BROWNE_TICKERS", "VT,TLT,SHY,GLD")

# Advanced: [azionario, obbligazionario_lungo, obbligazionario_breve, oro, immobiliare]
# ETF diversi da Harry Browne per non sovrapporre le due strategie.
ADVANCED_TICKERS = _list("ADVANCED_TICKERS", "VTI,EDV,VGSH,IAU,VNQ")
ADVANCED_SMA_PERIOD = _int("ADVANCED_SMA_PERIOD", 10)
# Il corso dà solo un'unica quota "obbligazioni" per profilo di rischio; non
# specifica come dividerla tra obbligazionario lungo e breve termine. Assunzione
# esplicita (non dal corso): split configurabile, default 50/50.
ADVANCED_BOND_LONG_SPLIT = _float("ADVANCED_BOND_LONG_SPLIT", 0.5)

# Ribilanciamento Harry Browne/Advanced a data fissa (non a soglia di scostamento)
REBALANCE_FREQUENCY = os.getenv("REBALANCE_FREQUENCY", "quarterly")  # quarterly|semiannual|annual

# Quale portafoglio di lungo termine gestire in AUTOMATICO nello scheduler
# (vedi bot.py:run_long_term_cycle): "advanced" (dentro/fuori per asset
# sulla SMA10 mensile, una decisione al mese), "harry_browne"
# (ribilanciamento al 25% a ogni REBALANCE_FREQUENCY) oppure "none" (solo
# a mano con long-term-status / long-term-pac). Il ciclo e' idempotente:
# gira ogni giorno insieme al breve termine ma agisce una sola volta per
# mese/trimestre, cosi' un giorno festivo o un server spento non lo salta.
LONG_TERM_AUTO_STRATEGY = os.getenv("LONG_TERM_AUTO_STRATEGY", "advanced").strip().lower()
if LONG_TERM_AUTO_STRATEGY not in ("advanced", "harry_browne", "none"):
    raise RuntimeError(f"LONG_TERM_AUTO_STRATEGY={LONG_TERM_AUTO_STRATEGY!r}: usa advanced, harry_browne o none")


# --- Breve termine (short_term/) -------------------------------------------
SHORT_TERM_CAPITAL = _float("SHORT_TERM_CAPITAL", 10_000.0)
# Universo validato nel backtest storico 2000-2026 (vedi STRATEGY.md):
# blue chip stabili + titoli a maggiore crescita/volatilità, dove un
# sistema trend-following storicamente rende meglio (vedi analisi in
# STRATEGY.md, "Risultati del backtest storico") + 8 ADR di grandi aziende
# non-USA (Toyota, ASML, TSMC, Novo Nordisk, TotalEnergies, Rio Tinto,
# Sony, BHP) validate separatamente nello stesso backtest (win rate
# 54-75%, PnL positivo su tutte e 8): diversificazione oltre i soliti nomi
# USA, ma solo quelle con un riscontro storico reale, non un'aggiunta a
# caso -- le altre 17 ADR testate erano deboli o in perdita, escluse.
SHORT_TERM_WATCHLIST = _list(
    "SHORT_TERM_WATCHLIST",
    "AAPL,MSFT,INTC,IBM,JPM,XOM,WMT,KO,JNJ,PG,HD,CAT,GE,DIS,CSCO,MCD,PFE,VZ,"
    "CVX,MMM,AMZN,NVDA,NFLX,ADBE,CRM,GOOGL,NKE,COST,QCOM,AMAT,TSLA,META,V,MA,"
    "ASML,TM,TSM,NVO,TTE,RIO,SONY,BHP",
)

# Se true, ignora SHORT_TERM_WATCHLIST e scansiona l'intero mercato USA
# (tutti i titoli tradable via Alpaca su NYSE/NASDAQ/ARCA/AMEX/BATS), con un
# prefiltro di liquidità prima della pipeline completa -- vedi
# short_term/screener.py:build_full_market_universe e STRATEGY.md. Richiede
# le chiavi Alpaca anche solo per lo screening (la watchlist statica no).
SHORT_TERM_USE_FULL_MARKET = _bool("SHORT_TERM_USE_FULL_MARKET", True)
# Prefiltro full-market: prezzo minimo (evita penny stock), volume$ medio
# minimo (liquidità sufficiente per entrare/uscire senza slippage eccessivo)
# e volume in pezzi minimo (corso, video 18: azioni singole sopra ~100.000
# scambi medi giornalieri).
SHORT_TERM_MIN_PRICE_FULL_MARKET = _float("SHORT_TERM_MIN_PRICE_FULL_MARKET", 10.0)
SHORT_TERM_MIN_DOLLAR_VOLUME = _float("SHORT_TERM_MIN_DOLLAR_VOLUME", 5_000_000.0)
SHORT_TERM_MIN_SHARE_VOLUME = _float("SHORT_TERM_MIN_SHARE_VOLUME", 100_000.0)
# Tetto al numero di titoli passati alla pipeline completa dopo il
# prefiltro (i migliori per volume$), per tenere sotto controllo i tempi di
# scansione quando l'universo full-market è di migliaia di titoli.
SHORT_TERM_FULL_MARKET_MAX_SYMBOLS = _int("SHORT_TERM_FULL_MARKET_MAX_SYMBOLS", 300)
# Volatilità storica annualizzata minima (STRATEGY.md "v4"): il backtest ha
# mostrato che un prefiltro di sola liquidità lascia passare titoli
# difensivi a bassa volatilità (utility, beni di consumo) su cui un
# sistema trend-following rende storicamente peggio. 25% è vicino alla
# volatilità storica di un blue chip "normale" (es. IBM) -- esclude le
# difensive più piatte, non i titoli con un minimo di movimento reale.
SHORT_TERM_MIN_ANNUALIZED_VOLATILITY_PCT = _float("SHORT_TERM_MIN_ANNUALIZED_VOLATILITY_PCT", 25.0)

SHORT_TERM_ACCOUNT_CURRENCY = os.getenv("SHORT_TERM_ACCOUNT_CURRENCY", "USD")
SHORT_TERM_FX_RATE = _float("SHORT_TERM_FX_RATE", 1.0)  # unità valuta conto per 1 USD

# Money management (STRATEGY.md 2.7): 1-2% per operazione, 0.5-1% per chi inizia
SHORT_TERM_RISK_PER_TRADE_PCT = _float("SHORT_TERM_RISK_PER_TRADE_PCT", 1.0)
SHORT_TERM_MAX_AGGREGATE_RISK_PCT = _float("SHORT_TERM_MAX_AGGREGATE_RISK_PCT", 12.0)

# Qualificazione trend (STRATEGY.md 2.1)
TREND_LOOKBACK_DAYS = _int("TREND_LOOKBACK_DAYS", 60)  # ~2-3 mesi
TREND_MIN_QUALIFIERS = _int("TREND_MIN_QUALIFIERS", 2)
TREND_PERFORMANCE_THRESHOLD_PCT = _float("TREND_PERFORMANCE_THRESHOLD_PCT", 30.0)
TREND_ADX_THRESHOLD = _float("TREND_ADX_THRESHOLD", 30.0)
TREND_PERSISTENCE_WINDOW = _int("TREND_PERSISTENCE_WINDOW", 20)
# Movimento netto minimo (%) sulla finestra di persistenza perché conti come
# "diretto" e non solo "ben adattato a una retta" -- una retta piatta si
# adatta perfettamente anche a un mercato laterale, quindi senza questo
# controllo il qualificatore di persistenza risultava vero anche in
# direzioni sbagliate o su dati piatti (bug trovato con stress-test
# sintetico, vedi STRATEGY.md). Scala TREND_PERFORMANCE_THRESHOLD_PCT in
# proporzione alla finestra più corta della persistenza.
PERSISTENCE_MIN_NET_MOVE_PCT = _float(
    "PERSISTENCE_MIN_NET_MOVE_PCT", TREND_PERFORMANCE_THRESHOLD_PCT * TREND_PERSISTENCE_WINDOW / TREND_LOOKBACK_DAYS
)

# "Ampio range" (qualificatore #3, STRATEGY.md 2.1) = range della barra >=
# 1.5x la volatilità media (Indicatore di Volatilità, video 39/41). Il corso
# non dà un numero, solo "sopra la media" -- 1.5x è la convenzione standard
# di analisi tecnica per una "wide-range bar" (range oltre un multiplo del
# range medio/ATR, vedi ricerca in STRATEGY.md).
WIDE_RANGE_ATR_MULT = _float("WIDE_RANGE_ATR_MULT", 1.5)

# Gap (qualificatore #2, STRATEGY.md 2.1) = apertura oltre questo multiplo
# della volatilità media dalla chiusura precedente. Sostituisce una soglia
# % fissa (che non si adatta alla volatilità del singolo titolo): la
# ricerca su gap/ATR-based thresholds indica la soglia relativa come
# convenzione superiore e standard (vedi STRATEGY.md).
GAP_VOLATILITY_MULT = _float("GAP_VOLATILITY_MULT", 0.5)

# Separazione minima (% del prezzo) tra EMA brevi e lunghe perché il fascio
# (STRATEGY.md 2.6) conti come "pulito" e non solo tecnicamente ordinato ma
# quasi a contatto. Il corso non dà un numero, solo "intrecciate sì/no".
RIBBON_MIN_SEPARATION_PCT = _float("RIBBON_MIN_SEPARATION_PCT", 0.3)

# Livelli entrata/stop (STRATEGY.md 2.4): "indicatore di volatilità" = media
# mobile del range (max-min) sulle ultime N barre
VOLATILITY_PERIOD = _int("VOLATILITY_PERIOD", 10)

# Filtri di rischio (STRATEGY.md 2.5)
EARNINGS_WARNING_DAYS = _int("EARNINGS_WARNING_DAYS", 15)
SUPPORT_RESISTANCE_MIN_R_MULTIPLE = _float("SUPPORT_RESISTANCE_MIN_R_MULTIPLE", 3.0)
SHORT_MIN_PRICE = _float("SHORT_MIN_PRICE", 80.0)

# Settori: ETF SPDR come proxy dei sotto-indici Dow Jones citati nel corso
SECTOR_RS_LOOKBACK_DAYS = _int("SECTOR_RS_LOOKBACK_DAYS", 60)

# Filtro di regime di mercato (STRATEGY.md "v5", validato nel backtest):
# long solo se l'indice (SPY) chiude sopra la sua SMA di lungo periodo,
# short solo se sotto. Estende lo Step 2 del corso (titolo e settore
# allineati al mercato) all'indice stesso; letteratura: Faber 2007,
# rendimento dell'S&P 500 sopra/sotto la SMA200.
MARKET_REGIME_FILTER = _bool("MARKET_REGIME_FILTER", True)
MARKET_REGIME_MA_PERIOD = _int("MARKET_REGIME_MA_PERIOD", 200)

# Operazioni short (STRATEGY.md "v6"): il corso le prevede e il codice le
# implementa per intero, ma in OGNI backtest 2000-2026 (v1-v5) il lato
# short e' in perdita netta (Profit Factor ~0.7) anche col filtro di
# regime, mentre toglierle migliora tutte le metriche (Sharpe 0.52 -> 0.61,
# drawdown -15.7% -> -13.0%). Default: solo long. Mettere true per
# riattivare gli short come da corso.
SHORT_TERM_ALLOW_SHORTS = _bool("SHORT_TERM_ALLOW_SHORTS", False)

# Freno di drawdown: se l'equity del conto e' sotto il massimo dell'ultimo
# anno di piu' di questa %, il bot NON apre nuove posizioni (gestisce solo
# quelle aperte) finche' non recupera.
#
# DISATTIVATO DI DEFAULT (0) sulla base del backtest, non per svista. Al
# 15% e' stato misurato su 26 anni e PEGGIORA entrambe le metriche che
# dovrebbe proteggere: CAGR +8.40% -> +7.35% e soprattutto max drawdown
# -20.2% -> -33.8% (vedi STRATEGY.md "v8b"). Il motivo e' che blocca le
# entrate dopo le perdite, cioe' vicino ai minimi, e tiene il bot fuori
# dal mercato proprio durante il rimbalzo: la discesa non viene fermata,
# il recupero sì. Il rischio per operazione (1%) e il tetto aggregato
# (12%) restano i veri controlli del drawdown, come nel corso.
SHORT_TERM_MAX_DRAWDOWN_PCT = _float("SHORT_TERM_MAX_DRAWDOWN_PCT", 0.0)

# Un ordine d'ingresso pendente (buy stop) resta valido finche' il titolo
# continua a mostrare il setup allo screening quotidiano (come nel
# backtest: pendente aggiornato o cancellato a ogni scansione); questo e'
# solo un tetto di sicurezza in giorni di calendario oltre il quale viene
# cancellato comunque.
SHORT_TERM_PENDING_MAX_DAYS = _int("SHORT_TERM_PENDING_MAX_DAYS", 20)
