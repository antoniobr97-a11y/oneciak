"""Money management: position sizing, rischio aggregato, matematica del
drawdown, Profit Factor. Vedi STRATEGY.md 2.7."""
import math

from common import config


def position_size(capital: float, risk_pct: float, risk_per_share: float, fx_rate: float = 1.0) -> int:
    """numero_azioni = floor((capitale * rischio%) / (rischio_per_azione / cambio_valuta))"""
    if risk_per_share <= 0:
        return 0
    risk_amount = capital * (risk_pct / 100)
    return max(0, math.floor(risk_amount / (risk_per_share / fx_rate)))


def aggregate_risk_pct(open_positions_count: int, risk_pct_per_trade: float | None = None) -> float:
    risk_pct_per_trade = risk_pct_per_trade if risk_pct_per_trade is not None else config.SHORT_TERM_RISK_PER_TRADE_PCT
    return open_positions_count * risk_pct_per_trade


def can_open_new_position(open_positions_count: int, risk_pct_per_trade: float | None = None) -> bool:
    """Vero se aprire una nuova posizione non supera il tetto di rischio
    aggregato (10-12% dello scenario peggiore, tutte a stop-loss insieme)."""
    projected = aggregate_risk_pct(open_positions_count + 1, risk_pct_per_trade)
    return projected <= config.SHORT_TERM_MAX_AGGREGATE_RISK_PCT


def drawdown_recovery_pct(drawdown_pct: float) -> float:
    """Guadagno % necessario per recuperare un drawdown %. La matematica è
    fortemente asimmetrica: -20% richiede +25%, -50% richiede +100%, -70%
    richiede +233%."""
    if not 0 <= drawdown_pct < 100:
        raise ValueError("drawdown_pct must be in [0, 100)")
    remaining = 1 - drawdown_pct / 100
    return (1 / remaining - 1) * 100


def profit_factor(trade_pnls: list[float]) -> float:
    """Profit Factor = somma(guadagni) / somma(|perdite|). Da monitorare
    ogni 3-6 mesi, non per singolo trade. Ritorna inf se non ci sono perdite
    e almeno un guadagno; 0.0 se non ci sono trade."""
    gains = sum(p for p in trade_pnls if p > 0)
    losses = sum(-p for p in trade_pnls if p < 0)
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return gains / losses
