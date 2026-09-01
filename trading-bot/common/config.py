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

RUN_TIME = os.getenv("RUN_TIME", "15:50")


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


# --- Breve termine (short_term/) -------------------------------------------
SHORT_TERM_CAPITAL = _float("SHORT_TERM_CAPITAL", 10_000.0)
SHORT_TERM_WATCHLIST = _list(
    "SHORT_TERM_WATCHLIST",
    "AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,AMD,NFLX,CRM",
)
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

# Livelli entrata/stop (STRATEGY.md 2.4): "indicatore di volatilità" = media
# mobile del range (max-min) sulle ultime N barre
VOLATILITY_PERIOD = _int("VOLATILITY_PERIOD", 10)

# Filtri di rischio (STRATEGY.md 2.5)
EARNINGS_WARNING_DAYS = _int("EARNINGS_WARNING_DAYS", 15)
SUPPORT_RESISTANCE_MIN_R_MULTIPLE = _float("SUPPORT_RESISTANCE_MIN_R_MULTIPLE", 3.0)
SHORT_MIN_PRICE = _float("SHORT_MIN_PRICE", 80.0)

# Settori: ETF SPDR come proxy dei sotto-indici Dow Jones citati nel corso
SECTOR_RS_LOOKBACK_DAYS = _int("SECTOR_RS_LOOKBACK_DAYS", 60)
