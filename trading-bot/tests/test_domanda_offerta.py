"""Ricostruzione dell'indicatore domanda/offerta del corso (video 39).

Il corso lo dichiara proprietario e non ne da' la formula; questa e' una
ricostruzione con la scomposizione classica del volume (termine CLV
dell'Accumulation/Distribution di Chaikin). I test fissano le proprieta'
che la ricostruzione deve avere, non un risultato ottenuto a posteriori.
"""

import numpy as np
import pandas as pd
import pytest

from short_term.indicators import domanda_offerta, domanda_supera_offerta


def _barre(chiusure, massimo=10.0, minimo=8.0, volume=1000.0):
    n = len(chiusure)
    return (
        pd.Series([massimo] * n, dtype=float),
        pd.Series([minimo] * n, dtype=float),
        pd.Series(chiusure, dtype=float),
        pd.Series([volume] * n, dtype=float),
    )


def test_domanda_piu_offerta_fanno_il_volume():
    """Ogni scambio va a una delle due parti: niente si perde, niente si inventa."""
    h, l, c, v = _barre([8.0, 8.5, 9.0, 9.5, 10.0, 9.2, 8.8, 9.9])

    domanda, offerta = domanda_offerta(h, l, c, v, 8)

    assert domanda.iloc[-1] + offerta.iloc[-1] == pytest.approx(1000.0)


def test_chiusura_sul_massimo_e_tutta_domanda():
    h, l, c, v = _barre([10.0] * 8)

    domanda, offerta = domanda_offerta(h, l, c, v, 8)

    assert domanda.iloc[-1] == pytest.approx(1000.0)
    assert offerta.iloc[-1] == pytest.approx(0.0)


def test_chiusura_sul_minimo_e_tutta_offerta():
    h, l, c, v = _barre([8.0] * 8)

    domanda, offerta = domanda_offerta(h, l, c, v, 8)

    assert domanda.iloc[-1] == pytest.approx(0.0)
    assert offerta.iloc[-1] == pytest.approx(1000.0)


def test_barra_piatta_resta_neutra():
    """Massimo == minimo: non c'e' modo di sapere chi ha comprato.

    Si divide a meta' invece di attribuire tutto a una parte (e invece di
    dividere per zero)."""
    n = 8
    h = pd.Series([9.0] * n, dtype=float)
    l = pd.Series([9.0] * n, dtype=float)
    c = pd.Series([9.0] * n, dtype=float)
    v = pd.Series([1000.0] * n, dtype=float)

    domanda, offerta = domanda_offerta(h, l, c, v, n)

    assert domanda.iloc[-1] == pytest.approx(500.0)
    assert offerta.iloc[-1] == pytest.approx(500.0)
    assert np.isfinite(domanda.iloc[-1])


def test_il_verde_sta_sopra_al_rosso_quando_si_chiude_in_alto():
    h, l, c, v = _barre([9.9] * 8)

    assert bool(domanda_supera_offerta(h, l, c, v, 8).iloc[-1]) is True


def test_il_verde_sta_sotto_al_rosso_quando_si_chiude_in_basso():
    h, l, c, v = _barre([8.1] * 8)

    assert bool(domanda_supera_offerta(h, l, c, v, 8).iloc[-1]) is False


def test_senza_storico_sufficiente_non_si_conferma():
    """Meno di `period` barre: nessun dato, quindi nessuna conferma.

    Deve essere False, non NaN e non True: un indicatore che non sa non
    deve lasciar passare il trade."""
    h, l, c, v = _barre([9.9] * 5)

    segnale = domanda_supera_offerta(h, l, c, v, 8)

    assert segnale.dtype == bool
    assert not segnale.any()


def test_i_periodi_del_corso_sono_8_e_14():
    """Il corso: domanda-offerta a 8 periodi, versione 3 a 14."""
    chiusure = [8.0, 8.2, 8.4, 9.0, 9.5, 9.8, 10.0, 9.9, 9.7, 9.4, 9.1, 8.9, 8.6, 8.3]
    h, l, c, v = _barre(chiusure)

    a8 = domanda_offerta(h, l, c, v, 8)[0]
    a14 = domanda_offerta(h, l, c, v, 14)[0]

    assert a8.notna().sum() == len(chiusure) - 8 + 1
    assert a14.notna().sum() == 1
    assert a8.iloc[-1] != a14.iloc[-1]
