"""I 7 pattern (6 di continuazione + 1 di inversione). Vedi STRATEGY.md 2.2.

Un pattern non è un segnale di ingresso -- è "vale la pena continuare
l'analisi" (calcolare i livelli in levels.py). Tutti i pattern di
continuazione condividono il concetto di "barra di setup": la barra del
pullback con l'estremo più profondo raggiunto finora. Le barre inside
(range contenuto in quello della barra precedente) non contano ai fini del
conteggio delle barre di pullback.

Nota dichiarata in STRATEGY.md: Pullback Semplice + TKO coprono da soli
circa il 90% delle operazioni di continuazione -- sono i due implementati
con la maggior copertura di test. Gli altri 4 sono varianti per situazioni
meno nitide.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from common import config
from short_term.indicators import adx, ema, sma
from short_term.trend import is_wide_range_bar, persistence_qualifier

BOWAI_EXTREME_LOOKBACK = 126  # ~6 mesi di borsa
BOWAI_INVERSION_WINDOW = 5  # "inverte l'ordine in <=5 giorni"
# Corso (video 29): il pullback semplice ha massimi E minimi decrescenti
# barra dopo barra. True = regola del corso; False = solo i massimi (la
# versione con cui sono stati fatti i backtest v1-v6, vedi STRATEGY.md v10).
PULLBACK_REQUIRE_LOWS = True


@dataclass
class PatternMatch:
    pattern: str
    direction: str
    setup_bar_index: int  # barra di riferimento per l'ENTRATA (sopra il suo massimo / sotto il suo minimo)
    pullback_bar_count: int
    details: str = ""
    # Barra di riferimento per lo STOP quando e' diversa da quella di
    # entrata: il corso (video 32/33) entra sopra il massimo della barra di
    # pivot / del breakout fallito, ma mette lo stop "sotto il minimo piu'
    # basso del pullback". None = stessa barra dell'entrata.
    stop_bar_index: int | None = None


def _deepest_bar(df: pd.DataFrame, direction: str, positions: list[int]) -> int:
    """Barra con il minimo piu' basso (long) / massimo piu' alto (short)
    tra quelle indicate: e' il riferimento dello stop-loss del corso."""
    if direction == "long":
        return min(positions, key=lambda p: df["low"].iloc[p])
    return max(positions, key=lambda p: df["high"].iloc[p])


def _is_inside_bar(df: pd.DataFrame, pos: int) -> bool:
    if pos == 0:
        return False
    return bool(df["high"].iloc[pos] <= df["high"].iloc[pos - 1] and df["low"].iloc[pos] >= df["low"].iloc[pos - 1])


def _window(df: pd.DataFrame, lookback: int) -> pd.DataFrame:
    return df.iloc[-lookback:] if len(df) > lookback else df


def _recent_extreme_pos(df: pd.DataFrame, direction: str, lookback: int) -> int | None:
    """Posizione del massimo (long) / minimo (short) piu' recente nella
    finestra.

    Aritmetica sulle POSIZIONI, non sulle etichette dell'indice: con
    `idxmax()` + `index.get_loc()` una data duplicata nei dati -- capita
    con i dati Yahoo -- fa restituire a get_loc uno slice invece di un
    intero, e tutto il resto della funzione salta. Il risultato e'
    identico su dati ben formati."""
    w = _window(df, lookback)
    if len(w) == 0:
        return None
    values = (w["high"] if direction == "long" else w["low"]).to_numpy(dtype=float)
    if np.all(np.isnan(values)):
        return None
    pos = int(np.nanargmax(values)) if direction == "long" else int(np.nanargmin(values))
    return len(df) - len(w) + pos


def _pullback_segment(df: pd.DataFrame, direction: str, peak_pos: int) -> tuple[list[int], int | None]:
    """Barre non-inside dopo l'estremo, e posizione della barra di setup
    (estremo del ritracciamento più profondo raggiunto finora)."""
    non_inside: list[int] = []
    setup_pos = None
    setup_extreme = None
    for pos in range(peak_pos + 1, len(df)):
        if _is_inside_bar(df, pos):
            continue
        non_inside.append(pos)
        val = df["low"].iloc[pos] if direction == "long" else df["high"].iloc[pos]
        if setup_extreme is None or (val < setup_extreme if direction == "long" else val > setup_extreme):
            setup_extreme = val
            setup_pos = pos
    return non_inside, setup_pos


def detect_pullback_semplice(df: pd.DataFrame, direction: str, lookback: int | None = None) -> PatternMatch | None:
    lookback = lookback or config.TREND_LOOKBACK_DAYS
    peak_pos = _recent_extreme_pos(df, direction, lookback)
    if peak_pos is None:
        return None
    non_inside, setup_pos = _pullback_segment(df, direction, peak_pos)
    if setup_pos is None or not (2 <= len(non_inside) <= 7):
        return None

    # Corso (video 29): il ritracciamento e' una sequenza di massimi E
    # minimi decrescenti (long) / crescenti (short), barra dopo barra --
    # entrambe le serie, non solo una.
    highs = [df["high"].iloc[p] for p in non_inside]
    lows = [df["low"].iloc[p] for p in non_inside]
    if direction == "long":
        harmonic = all(b <= a for a, b in zip(highs, highs[1:]))
        if PULLBACK_REQUIRE_LOWS:
            harmonic = harmonic and all(b <= a for a, b in zip(lows, lows[1:]))
    else:
        harmonic = all(b >= a for a, b in zip(lows, lows[1:]))
        if PULLBACK_REQUIRE_LOWS:
            harmonic = harmonic and all(b >= a for a, b in zip(highs, highs[1:]))
    if not harmonic:
        return None

    return PatternMatch("Pullback Semplice", direction, setup_pos, len(non_inside))


def detect_tko(df: pd.DataFrame, direction: str, lookback: int | None = None) -> PatternMatch | None:
    lookback = lookback or config.TREND_LOOKBACK_DAYS
    peak_pos = _recent_extreme_pos(df, direction, lookback)
    if peak_pos is None:
        return None
    non_inside, _ = _pullback_segment(df, direction, peak_pos)
    if not non_inside or len(non_inside) > 7:
        return None

    last_pos = non_inside[-1]
    if not is_wide_range_bar(df, last_pos):
        return None

    prior_start = max(0, last_pos - 5)
    if direction == "long":
        broken = int((df["low"].iloc[prior_start:last_pos] > df["low"].iloc[last_pos]).sum())
    else:
        broken = int((df["high"].iloc[prior_start:last_pos] < df["high"].iloc[last_pos]).sum())
    if broken < 2:
        return None

    return PatternMatch("TKO", direction, last_pos, len(non_inside))


def detect_pullback_persistente(df: pd.DataFrame, direction: str, lookback: int | None = None) -> PatternMatch | None:
    lookback = lookback or config.TREND_LOOKBACK_DAYS
    peak_pos = _recent_extreme_pos(df, direction, lookback)
    if peak_pos is None:
        return None
    pre_peak = df.iloc[: peak_pos + 1]
    if not persistence_qualifier(pre_peak, direction):
        return None

    match = detect_pullback_semplice(df, direction, lookback)
    if match is None:
        return None
    return PatternMatch("Pullback Persistente", direction, match.setup_bar_index, match.pullback_bar_count)


def detect_trend_pivot_pullback(df: pd.DataFrame, direction: str, lookback: int | None = None) -> PatternMatch | None:
    lookback = lookback or config.TREND_LOOKBACK_DAYS
    peak_pos = _recent_extreme_pos(df, direction, lookback)
    if peak_pos is None:
        return None
    non_inside, _ = _pullback_segment(df, direction, peak_pos)
    if not (3 <= len(non_inside) <= 5):
        return None

    for k in range(1, len(non_inside) - 1):
        a, b, c = non_inside[k - 1], non_inside[k], non_inside[k + 1]
        if direction == "long":
            is_pivot = df["high"].iloc[b] > df["high"].iloc[a] and df["high"].iloc[b] > df["high"].iloc[c]
            failed = df["low"].iloc[c] < df["low"].iloc[a]
        else:
            is_pivot = df["low"].iloc[b] < df["low"].iloc[a] and df["low"].iloc[b] < df["low"].iloc[c]
            failed = df["high"].iloc[c] > df["high"].iloc[a]
        if is_pivot and failed:
            # Corso (video 32): ingresso sopra il massimo della barra di
            # PIVOT (quella centrale), stop sotto il minimo piu' basso del
            # pullback (la barra successiva, che ha "fallito").
            return PatternMatch(
                "Trend Pivot Pullback", direction, b, len(non_inside),
                stop_bar_index=_deepest_bar(df, direction, non_inside),
            )
    return None


def detect_second_entry_pullback(df: pd.DataFrame, direction: str, lookback: int | None = None) -> PatternMatch | None:
    lookback = lookback or config.TREND_LOOKBACK_DAYS
    peak_pos = _recent_extreme_pos(df, direction, lookback)
    if peak_pos is None:
        return None
    non_inside, _ = _pullback_segment(df, direction, peak_pos)
    if not (2 <= len(non_inside) <= 5):
        return None

    for k in range(1, len(non_inside)):
        prev_pos, cur_pos = non_inside[k - 1], non_inside[k]
        if direction == "long":
            failed_breakout = (
                df["high"].iloc[cur_pos] > df["high"].iloc[prev_pos]
                and df["close"].iloc[cur_pos] < df["high"].iloc[prev_pos]
            )
        else:
            failed_breakout = (
                df["low"].iloc[cur_pos] < df["low"].iloc[prev_pos]
                and df["close"].iloc[cur_pos] > df["low"].iloc[prev_pos]
            )
        if failed_breakout:
            # Corso (video 33): ingresso sopra il massimo della barra del
            # breakout fallito, stop "sotto il minimo piu' basso del pullback".
            return PatternMatch(
                "Second Entry Pullback", direction, cur_pos, len(non_inside),
                stop_bar_index=_deepest_bar(df, direction, non_inside),
            )
    return None


def detect_sacro_graal(df: pd.DataFrame, direction: str, lookback: int | None = None) -> PatternMatch | None:
    lookback = lookback or config.TREND_LOOKBACK_DAYS
    if len(df) < 2:
        return None
    # "ADX >30 e crescente" misurato da una barra all'altra SULLA barra di
    # ritracciamento. Letteralmente e' una contraddizione -- durante un
    # ritracciamento l'ADX scende per costruzione, e infatti 240 setup
    # sintetici da manuale falliscono tutti e 240 su questa condizione --
    # e il risultato e' che il Sacro Graal quasi non scatta mai: 5
    # operazioni in 26 anni di backtest.
    #
    # E' STATO CORRETTO E MISURATO (STRATEGY.md "v13"): misurando l'ADX al
    # picco, prima del ritracciamento, sulla stessa finestra di 10 barre
    # usata da trend.adx_qualifier, il pattern scatta 500 volte e diventa
    # il piu' frequente -- ma il capitale finale su 26 anni scende da
    # 120.214 a 102.349, lo Sharpe da 0.87 a 0.81, il Profit Factor da
    # 1.72 a 1.60. Il motivo e' che quei 500 setup occupano i posti del
    # tetto di rischio a scapito di pattern storicamente migliori (Second
    # Entry passa da 496 a 394, Pullback Semplice da 329 a 239).
    #
    # Si tiene quindi la versione restrittiva: non per svista, ma perche'
    # la misura dice che l'alternativa fedele alla lettera rende meno.
    adx_series = adx(df["high"], df["low"], df["close"], 14)
    if adx_series.isna().iloc[-1] or adx_series.isna().iloc[-2]:
        return None
    if not (adx_series.iloc[-1] > config.TREND_ADX_THRESHOLD and adx_series.iloc[-1] > adx_series.iloc[-2]):
        return None

    peak_pos = _recent_extreme_pos(df, direction, lookback)
    if peak_pos is None:
        return None
    non_inside, _ = _pullback_segment(df, direction, peak_pos)
    if not non_inside:
        return None

    ema20 = ema(df["close"], 20)
    last_pos = non_inside[-1]
    if pd.isna(ema20.iloc[last_pos]):
        return None
    touched = df["low"].iloc[last_pos] <= ema20.iloc[last_pos] <= df["high"].iloc[last_pos]
    if not touched:
        return None

    return PatternMatch("Sacro Graal", direction, last_pos, len(non_inside))


def detect_bowai(df: pd.DataFrame, direction: str) -> PatternMatch | None:
    """Pattern di inversione: SMA10/EMA20/EMA30 invertono l'ordine in <=5
    giorni, dopo un minimo (long) o massimo (short) di almeno ~6 mesi."""
    if len(df) < BOWAI_EXTREME_LOOKBACK + BOWAI_INVERSION_WINDOW:
        return None

    sma10, ema20, ema30 = sma(df["close"], 10), ema(df["close"], 20), ema(df["close"], 30)
    lines = pd.DataFrame({"sma10": sma10, "ema20": ema20, "ema30": ema30})
    recent = lines.iloc[-(BOWAI_INVERSION_WINDOW + 1):]
    if recent.isna().any().any():
        return None

    before, after = recent.iloc[0], recent.iloc[-1]
    if direction == "long":
        inverted = (
            before["sma10"] < before["ema20"] < before["ema30"]
            and after["sma10"] > after["ema20"] > after["ema30"]
        )
    else:
        inverted = (
            before["sma10"] > before["ema20"] > before["ema30"]
            and after["sma10"] < after["ema20"] < after["ema30"]
        )
    if not inverted:
        return None

    # Il minimo/massimo di periodo deve appartenere alla fase di inversione
    # appena conclusa (non necessariamente l'ultima barra: il prezzo può
    # aver già ripreso a salire/scendere nei giorni della conferma).
    extreme_window = df.iloc[-(BOWAI_EXTREME_LOOKBACK + BOWAI_INVERSION_WINDOW):]
    if direction == "long":
        extreme_pos = int(np.argmin(extreme_window["low"].to_numpy()))
    else:
        extreme_pos = int(np.argmax(extreme_window["high"].to_numpy()))
    bars_since_extreme = len(extreme_window) - 1 - extreme_pos
    if bars_since_extreme > BOWAI_INVERSION_WINDOW + 5:
        return None

    return PatternMatch("Bowai", direction, len(df) - 1, pullback_bar_count=1)


CONTINUATION_DETECTORS = {
    "Pullback Semplice": detect_pullback_semplice,
    "TKO": detect_tko,
    "Pullback Persistente": detect_pullback_persistente,
    "Trend Pivot Pullback": detect_trend_pivot_pullback,
    "Second Entry Pullback": detect_second_entry_pullback,
    "Sacro Graal": detect_sacro_graal,
}


def _collapse_persistent_pullback(matches: list[PatternMatch]) -> list[PatternMatch]:
    """Il Pullback Persistente e' per costruzione un Pullback Semplice che
    supera in piu' il test di persistenza (lo chiama al suo interno):
    stessa barra di setup, stessi livelli, stessa operazione. Tenerli
    entrambi produceva due candidati identici sullo stesso titolo -- e
    misurato sui dati storici accadeva nel 100% dei casi in cui il
    Persistente scattava (40 su 40 nel campione).

    Costava due volte il lavoro di screener._build_candidate, che include
    chiamate di rete per settore e trimestrali, e soprattutto faceva
    sparire il nome piu' informativo: a parita' di punteggio la deduplica
    tiene il primo della lista, e "Pullback Semplice" viene prima. Su 26
    anni di backtest il Pullback Persistente non compare MAI fra le
    operazioni, pur essendo stato rilevato. Qui si tiene la
    classificazione piu' specifica; l'operazione non cambia di una virgola."""
    persistent = {m.setup_bar_index for m in matches if m.pattern == "Pullback Persistente"}
    if not persistent:
        return matches
    return [m for m in matches if not (m.pattern == "Pullback Semplice" and m.setup_bar_index in persistent)]


def detect_all(df: pd.DataFrame, direction: str, lookback: int | None = None) -> list[PatternMatch]:
    matches = []
    for detector in CONTINUATION_DETECTORS.values():
        match = detector(df, direction, lookback)
        if match is not None:
            matches.append(match)
    bowai = detect_bowai(df, direction)
    if bowai is not None:
        matches.append(bowai)
    return _collapse_persistent_pullback(matches)
