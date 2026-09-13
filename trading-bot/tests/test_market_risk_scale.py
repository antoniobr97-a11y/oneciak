"""Freno di volatilita' di mercato (RICERCA.md 2.1).

La regola e' semplice; i modi di sbagliarla non lo sono. Il piu' grave e'
lo sguardo al futuro: usare la barra di OGGI per decidere la size di OGGI
darebbe un backtest splendido e un bot inutile. Qui c'e' un test apposta."""
import math

import numpy as np
import pandas as pd
import pytest

from common import config
from short_term import money_management as mm


def _serie(rendimenti: list[float], base: float = 100.0) -> pd.Series:
    prezzi = [base]
    for r in rendimenti:
        prezzi.append(prezzi[-1] * (1 + r))
    return pd.Series(prezzi)


def _calma(n: int = 60) -> pd.Series:
    # ~6% annuo: ben sotto qualsiasi obiettivo ragionevole
    return _serie([0.06 / math.sqrt(252) * (1 if i % 2 else -1) for i in range(n)])


def _tempesta(n: int = 60, vol: float = 0.30) -> pd.Series:
    # 30% annuo di default: mercato nervoso ma non in panico -- il freno
    # lavora qui, fra il tetto e il pavimento.
    return _serie([vol / math.sqrt(252) * (1 if i % 2 else -1) for i in range(n)])


@pytest.fixture
def acceso(monkeypatch):
    monkeypatch.setattr(config, "MARKET_VOL_TARGET", 0.16)
    monkeypatch.setattr(config, "MARKET_VOL_LOOKBACK_DAYS", 21)
    monkeypatch.setattr(config, "MARKET_VOL_SCALE_FLOOR", 0.40)


def test_spento_per_default_non_tocca_niente(monkeypatch):
    monkeypatch.setattr(config, "MARKET_VOL_TARGET", 0.0)
    assert mm.market_risk_scale(_tempesta()) == 1.0


def test_mercato_calmo_nessun_freno(acceso):
    assert mm.market_risk_scale(_calma()) == 1.0


def test_mercato_in_tempesta_riduce_il_rischio(acceso):
    fattore = mm.market_risk_scale(_tempesta())
    assert fattore < 1.0
    assert fattore == pytest.approx(0.16 / 0.30, rel=0.15)


def test_mai_una_leva_il_tetto_e_uno(acceso):
    """Mercato piattissimo: il rapporto obiettivo/volatilita' esploderebbe.
    Il fattore deve restare 1.0, mai 3x o 10x."""
    piatto = _serie([0.0001 * (1 if i % 2 else -1) for i in range(60)])
    assert mm.market_risk_scale(piatto) == 1.0


def test_il_pavimento_limita_il_taglio(acceso):
    """Crollo estremo: il freno taglia, ma non azzera l'operativita'."""
    panico = _tempesta(vol=1.20)  # 120% annuo: marzo 2020 al suo peggio
    assert mm.market_risk_scale(panico) == 0.40


def test_storico_insufficiente_non_frena(acceso):
    """Nessun freno 'per sicurezza' non motivato dai dati: stessa scelta
    gia' fatta per il filtro di regime."""
    assert mm.market_risk_scale(_tempesta(n=5)) == 1.0
    assert mm.market_risk_scale(pd.Series([], dtype=float)) == 1.0
    assert mm.market_risk_scale(None) == 1.0


def test_non_guarda_il_futuro(acceso):
    """IL test che conta. La barra di OGGI non e' chiusa quando il bot
    decide la size: se la regola la usasse, aggiungere un crollo in fondo
    alla serie cambierebbe il fattore di oggi. Non deve cambiarlo."""
    calma = _calma(n=60)
    prima = mm.market_risk_scale(calma)

    crollo_oggi = pd.concat([calma, pd.Series([calma.iloc[-1] * 0.80])], ignore_index=True)
    dopo = mm.market_risk_scale(crollo_oggi)

    assert dopo == prima == 1.0, (
        "il crollo dell'ultima barra ha cambiato il fattore: la regola sta "
        "guardando una barra non ancora chiusa"
    )


def test_il_crollo_conta_dal_giorno_dopo(acceso):
    """Complemento del test precedente: il freno non deve essere cieco,
    solo ritardato di una barra. Il giorno DOPO il crollo deve reagire."""
    calma = _calma(n=60)
    crollo = pd.concat([calma, pd.Series([calma.iloc[-1] * 0.80,
                                          calma.iloc[-1] * 0.80])], ignore_index=True)
    assert mm.market_risk_scale(crollo) < 1.0


def test_nan_nei_prezzi_non_rompe_il_calcolo(acceso):
    con_buco = _calma(n=60)
    con_buco.iloc[30] = np.nan
    fattore = mm.market_risk_scale(con_buco)
    assert 0.40 <= fattore <= 1.0
    assert not math.isnan(fattore)


def test_il_fattore_moltiplica_davvero_la_size():
    """Il collegamento con il sizing: meta' rischio, circa meta' azioni."""
    piene = money_management_qty(1.0)
    ridotte = money_management_qty(0.5)
    assert ridotte == piene // 2


def money_management_qty(scala: float) -> int:
    return mm.position_size(100_000, 1.0 * scala, 2.0)
