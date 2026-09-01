"""Qualificazione del trend: 6 parametri, ne bastano 2-3 su 6 (raro
trovarli tutti). Vedi STRATEGY.md 2.1. Finestra tipica: ultimi 2-3 mesi."""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from common import config
from short_term.indicators import adx, avg_daily_range

# Non tutte le soglie sono numeri espliciti nel corso (es. "gap" e "barre ad
# ampio range" non hanno una soglia % dichiarata, sono giudizio visivo sul
# grafico) -- dove manca un numero preciso si usa una convenzione standard
# di analisi tecnica, documentata e configurabile in common/config.py,
# invece di un numero inventato a caso.
WIDE_RANGE_MIN_COUNT = 2
PERSISTENCE_TOLERANCE_ATR_MULT = 1.0


def is_wide_range_bar(df: pd.DataFrame, pos: int, period: int | None = None, mult: float | None = None) -> bool:
    """'Ampio range' = range della barra >= mult x la volatilità media
    (Indicatore di Volatilità, video 39/41) -- convenzione standard
    "wide-range bar = range oltre un multiplo dell'ATR/range medio"
    (default in config.WIDE_RANGE_ATR_MULT), non un percentile del periodo
    (che dipende troppo dalla finestra scelta)."""
    period = period or config.VOLATILITY_PERIOD
    mult = mult if mult is not None else config.WIDE_RANGE_ATR_MULT
    vol = avg_daily_range(df["high"], df["low"], period)
    if pos >= len(vol) or pd.isna(vol.iloc[pos]):
        return False
    bar_range = df["high"].iloc[pos] - df["low"].iloc[pos]
    return bool(bar_range >= mult * vol.iloc[pos])


@dataclass
class TrendQualification:
    direction: str
    score: int
    satisfied: dict[str, bool] = field(default_factory=dict)

    @property
    def qualifies(self) -> bool:
        return bool(self.score >= config.TREND_MIN_QUALIFIERS)


def _window(df: pd.DataFrame, lookback: int) -> pd.DataFrame:
    return df.iloc[-lookback:] if len(df) > lookback else df


def performance_qualifier(df: pd.DataFrame, direction: str, lookback: int) -> bool:
    w = _window(df, lookback)
    if len(w) < 2:
        return False
    if direction == "long":
        low_idx = w["low"].idxmin()
        after_low = w.loc[low_idx:]
        move_pct = (after_low["high"].max() / w["low"].min() - 1) * 100
    else:
        high_idx = w["high"].idxmax()
        after_high = w.loc[high_idx:]
        move_pct = (after_high["low"].min() / w["high"].max() - 1) * 100
    threshold = config.TREND_PERFORMANCE_THRESHOLD_PCT
    return move_pct >= threshold if direction == "long" else move_pct <= -threshold


def gap_qualifier(df: pd.DataFrame, direction: str, lookback: int) -> bool:
    """Gap = apertura abbastanza distante dalla chiusura precedente
    RISPETTO ALLA VOLATILITÀ PROPRIA del titolo (rapporto con
    l'Indicatore di Volatilità), non una % fissa uguale per tutti -- un
    gap dell'1% è enorme per un'utility poco volatile e insignificante
    per un titolo che si muove il 5% al giorno. Soglia relativa = la
    convenzione standard nella letteratura su gap/ATR-based thresholds
    (un valore fisso in punti percentuali è statico e non si adatta al
    titolo, vedi STRATEGY.md)."""
    w = _window(df, lookback)
    vol = avg_daily_range(df["high"], df["low"], config.VOLATILITY_PERIOD).reindex(w.index)
    prev_close = w["close"].shift(1)
    gap_ratio = (w["open"] - prev_close) / vol
    if direction == "long":
        return bool((gap_ratio >= config.GAP_VOLATILITY_MULT).fillna(False).any())
    return bool((gap_ratio <= -config.GAP_VOLATILITY_MULT).fillna(False).any())


def wide_range_qualifier(df: pd.DataFrame, direction: str, lookback: int) -> bool:
    w = _window(df, lookback)
    if len(w) < 10:
        return False
    vol = avg_daily_range(df["high"], df["low"], config.VOLATILITY_PERIOD).reindex(w.index)
    bar_range = w["high"] - w["low"]
    is_wide = bar_range >= config.WIDE_RANGE_ATR_MULT * vol

    close_position = (w["close"] - w["low"]) / bar_range.replace(0, np.nan)  # 0=low, 1=high
    if direction == "long":
        extreme_close = close_position >= 0.75
    else:
        extreme_close = close_position <= 0.25

    matches = (is_wide & extreme_close).fillna(False)
    return int(matches.sum()) >= WIDE_RANGE_MIN_COUNT


def _swing_points(series: pd.Series, order: int = 3) -> list[tuple[int, float]]:
    """Fractal di Williams: un punto è uno swing high/low se è l'estremo tra
    `order` barre prima e dopo (order=2 è la convenzione standard a 5
    barre; qui si usa order=2 sul giornaliero per l'armonia del trend, un
    order leggermente più ampio sul settimanale per i supporti/resistenze,
    dove si vogliono solo i livelli più significativi)."""
    points = []
    values = series.to_numpy()
    for i in range(order, len(values) - order):
        window = values[i - order: i + order + 1]
        if values[i] == window.max() or values[i] == window.min():
            points.append((i, values[i]))
    return points


def _mostly_monotonic(values: list[float], rising: bool) -> bool:
    """Vero se la sequenza è crescente/decrescente tollerando AL MASSIMO
    un'eccezione (STRATEGY.md 2.1: "una sequenza incoerente indebolisce la
    qualificazione" -- un'eccezione isolata non la invalida, più di una sì).
    Richiede almeno 4 punti (3 confronti) per essere un test significativo:
    con meno punti una "maggioranza" non dice quasi nulla sulla sequenza."""
    if len(values) < 4:
        return False
    pairs = list(zip(values, values[1:]))
    # Confronto stretto: un pareggio (b == a, es. su un mercato piatto) non
    # conta come "salente" né come "discendente" -- "not (b > a)" includeva
    # erroneamente il pareggio nel conteggio "discendente".
    agreeing = sum(1 for a, b in pairs if ((b > a) if rising else (b < a)))
    return agreeing >= len(pairs) - 1


def harmony_qualifier(df: pd.DataFrame, direction: str, lookback: int) -> bool:
    w = _window(df, lookback)
    if len(w) < 10:
        return False
    highs = _swing_points(w["high"], order=2)
    lows = _swing_points(w["low"], order=2)
    if len(highs) < 4 or len(lows) < 4:
        return False

    high_vals = [v for _, v in highs][-5:]
    low_vals = [v for _, v in lows][-5:]
    rising = direction == "long"
    return _mostly_monotonic(high_vals, rising) and _mostly_monotonic(low_vals, rising)


def adx_qualifier(df: pd.DataFrame, period: int = 14) -> bool:
    if len(df) == 0:
        return False
    adx_series = adx(df["high"], df["low"], df["close"], period)
    if adx_series.isna().iloc[-1]:
        return False
    last = adx_series.iloc[-1]
    if last > config.TREND_ADX_THRESHOLD:
        return True
    lookback_bars = min(10, len(adx_series) - 1)
    if lookback_bars <= 0 or adx_series.isna().iloc[-1 - lookback_bars]:
        return False
    return bool(last > adx_series.iloc[-1 - lookback_bars])


def persistence_qualifier(df: pd.DataFrame, direction: str, window: int | None = None) -> bool:
    """Una retta di tendenza (regressione lineare sulle chiusure) intercetta
    la maggior parte delle ultime N barre, entro una tolleranza -- E la
    retta deve puntare nella direzione testata con un movimento netto non
    trascurabile (altrimenti un mercato piatto o un rumore senza direzione
    "passa" il test per pura bontà di adattamento della retta, che è vero
    anche per una retta orizzontale -- bug trovato con dati sintetici)."""
    window = window or config.TREND_PERSISTENCE_WINDOW
    w = _window(df, window)
    if len(w) < window:
        return False

    closes = w["close"].to_numpy()
    x = np.arange(len(closes))
    slope, intercept = np.polyfit(x, closes, 1)
    fitted = slope * x + intercept

    atr_val = (w["high"] - w["low"]).mean()
    tolerance = atr_val * PERSISTENCE_TOLERANCE_ATR_MULT
    touches = np.abs(closes - fitted) <= tolerance
    tight_fit = touches.sum() >= len(closes) * 0.6

    net_move_pct = (closes[-1] - closes[0]) / closes[0] * 100
    min_move = config.PERSISTENCE_MIN_NET_MOVE_PCT
    directional = net_move_pct >= min_move if direction == "long" else net_move_pct <= -min_move
    return bool(tight_fit and directional)


def qualify_trend(df: pd.DataFrame, direction: str, lookback: int | None = None) -> TrendQualification:
    lookback = lookback or config.TREND_LOOKBACK_DAYS
    if len(df) == 0:
        return TrendQualification(direction=direction, score=0, satisfied={})
    checks = {
        "performance": performance_qualifier(df, direction, lookback),
        "gap": gap_qualifier(df, direction, lookback),
        "wide_range": wide_range_qualifier(df, direction, lookback),
        "harmony": harmony_qualifier(df, direction, lookback),
        "adx": adx_qualifier(df),
        "persistence": persistence_qualifier(df, direction),
    }
    return TrendQualification(direction=direction, score=int(sum(checks.values())), satisfied=checks)
