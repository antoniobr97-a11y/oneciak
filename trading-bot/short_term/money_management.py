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


def market_risk_scale(index_closes) -> float:
    """Fattore (0, 1] per cui moltiplicare il rischio per operazione, in
    base alla volatilita' realizzata del MERCATO (non del singolo titolo).

    Il sizing a rischio fisso gia' si adatta alla volatilita' del SINGOLO
    titolo, perche' lo stop e' piu' largo su un titolo nervoso e la size
    scende di conseguenza. Quello che NON fa e' accorgersi di quando e'
    tutto il mercato a essere nervoso -- ed e' li' che il momentum subisce
    i suoi crolli peggiori (Barroso & Santa-Clara 2015; Daniel & Moskowitz
    2016: i "momentum crash" si concentrano nelle fasi di alta volatilita'
    dell'indice, e scalare l'esposizione sulla volatilita' realizzata li
    attenua).

    Regola: fattore = obiettivo / volatilita' realizzata, limitato in
    [floor, 1.0]. Il tetto a 1.0 e' deliberato: e' un FRENO, mai un
    acceleratore. Nei mercati tranquilli il fattore e' 1.0 e la regola non
    tocca niente; taglia solo nelle fasi di stress vero.

    Ritorna 1.0 (nessun effetto) se la regola e' disattivata o se lo
    storico non basta: nessun freno "per sicurezza" non motivato dai dati,
    stessa scelta gia' fatta per il filtro di regime."""
    target = config.MARKET_VOL_TARGET
    if not target or target <= 0:
        return 1.0
    lookback = config.MARKET_VOL_LOOKBACK_DAYS
    if index_closes is None or len(index_closes) < lookback + 2:
        return 1.0
    # Volatilita' annualizzata dei rendimenti giornalieri sull'ultima
    # finestra CHIUSA. La barra di oggi non e' ancora finita quando il bot
    # decide la size, quindi va esclusa: usarla sarebbe guardare il futuro.
    returns = index_closes.pct_change().dropna()
    if len(returns) < lookback + 1:
        return 1.0
    realised = float(returns.iloc[-(lookback + 1):-1].std()) * math.sqrt(252)
    if not realised > 0 or math.isnan(realised):
        return 1.0
    return min(1.0, max(config.MARKET_VOL_SCALE_FLOOR, target / realised))


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
