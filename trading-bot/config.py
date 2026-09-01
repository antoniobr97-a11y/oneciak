"""Central configuration, loaded from environment variables (.env)."""
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


ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_PAPER = _bool("ALPACA_PAPER", True)

WATCHLIST = [s.strip().upper() for s in os.getenv("WATCHLIST", "AAPL,MSFT,SPY,QQQ").split(",") if s.strip()]

RISK_PER_TRADE_PCT = _float("RISK_PER_TRADE_PCT", 1.0)
MAX_POSITION_PCT = _float("MAX_POSITION_PCT", 20.0)

SMA_FAST = _int("SMA_FAST", 20)
SMA_SLOW = _int("SMA_SLOW", 50)
RSI_PERIOD = _int("RSI_PERIOD", 14)
RSI_OVERBOUGHT = _float("RSI_OVERBOUGHT", 70.0)
RSI_OVERSOLD = _float("RSI_OVERSOLD", 30.0)
ATR_PERIOD = _int("ATR_PERIOD", 14)
ATR_STOP_MULT = _float("ATR_STOP_MULT", 1.5)
REWARD_RISK_RATIO = _float("REWARD_RISK_RATIO", 2.0)

RUN_TIME = os.getenv("RUN_TIME", "15:50")


def require_alpaca_keys() -> None:
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        raise RuntimeError(
            "ALPACA_API_KEY / ALPACA_SECRET_KEY are not set. "
            "Copy .env.example to .env and fill in your paper trading keys."
        )
