"""L'esempio numerico del video 41 del corso, usato come test di regressione.

Il corso definisce l'"indicatore di volatilita'" come la media dell'ampiezza
delle barre giornaliere (massimo - minimo) sugli ultimi N giorni, con N = 10:

    "L'indicatore di volatilita' e' un indicatore che misura l'ampiezza media
     delle barre giornaliere [...] la differenza tra il massimo e il minimo
     della barra giornaliera"                                      (video 41)

    "La volatilita' in questo caso impostata a 10 periodi, quindi ci prende
     la media degli ultimi 10 giorni"                              (video 41)

e ne mostra un esempio svolto con i numeri:

    "la chiusura e' a 5,28, mentre il minimo e' a 5,22 [...] La volatilita'
     a 0,24: entrero' in acquisto a 5,28 + 0,24. Stop loss andra' impostato
     a 5,22 meno la volatilita', quindi -0,24 a 4,98 [...] Esattamente qua
     5,52 e 4,98."                                                 (video 41)

Se questi test falliscono, il bot non sta piu' calcolando entrata e stop come
il corso, ed e' un errore su OGNI ordine che manda.
"""

import pandas as pd

import common.config as config
from short_term.indicators import avg_daily_range
from short_term.levels import compute_levels


def test_esempio_svolto_del_video_41():
    """Chiusura 5,28 - minimo 5,22 - volatilita' 0,24 => entrata 5,52, stop 4,98."""
    setup_bar = pd.Series({"open": 5.25, "high": 5.30, "low": 5.22, "close": 5.28})

    livelli = compute_levels(setup_bar, 0.24, "long")

    assert round(livelli.entry, 2) == 5.52
    assert round(livelli.stop_loss, 2) == 4.98


def test_volatilita_e_la_media_dell_ampiezza_delle_barre():
    """Non e' l'ATR: il corso non include i gap, prende solo massimo - minimo."""
    high = pd.Series([10, 11, 12, 13, 14, 15, 16, 17, 18, 19], dtype=float)
    low = pd.Series([9, 10, 11, 11, 13, 13, 15, 16, 16, 18], dtype=float)

    atteso = (high - low).mean()

    assert avg_daily_range(high, low, 10).iloc[-1] == atteso


def test_il_bot_usa_i_10_periodi_del_corso():
    assert config.VOLATILITY_PERIOD == 10
