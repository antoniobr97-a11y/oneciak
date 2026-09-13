"""Trailing stop dopo 1R (STRATEGY.md "Trailing stop: misurato e adottato").

Il trailing tocca gli ordini di protezione di posizioni aperte con soldi
veri: ogni spostamento e' una cancellazione seguita da un reinvio, e fra
le due la posizione e' scoperta. I test qui sotto difendono, in ordine di
gravita':

  1. lo stop non torna MAI indietro (se lo facesse, il trailing non
     sarebbe una protezione ma una scommessa che peggiora nel tempo);
  2. non si tocca niente finche' la giornata non e' chiusa (il massimo di
     una giornata in corso non e' un massimo);
  3. se il reinvio fallisce, lo stato NON dice che si e' protetti.
"""
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

import bot
from common import config
from tests.test_bot import ENTERED_10, _broker, _order, _patched_state, _position


@pytest.fixture(autouse=True)
def trailing_acceso(monkeypatch):
    """Il trailing e' spento di default in configurazione: i test lo
    accendono esplicitamente, cosi' il valore di default resta una scelta
    documentata e non qualcosa che i test impongono di nascosto."""
    monkeypatch.setattr(bot, "TRAIL_ATR_MULT", 3.0)
    monkeypatch.setattr(bot, "TRAIL_ATR_PERIOD", 22)
    monkeypatch.setattr(bot, "TRAIL_MIN_MOVE_ATR", 0.0)


def test_spento_di_default_non_tocca_nessuno_stop(monkeypatch):
    """Con l'interruttore a 0 il comportamento e' identico a prima: nessun
    livello, quindi nessuna cancellazione di ordini di protezione."""
    monkeypatch.setattr(bot, "TRAIL_ATR_MULT", 0.0)
    assert bot._trailing_stop_level(_salita(), "long", None) is None


def _bars(closes, start="2026-01-01"):
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {"open": c, "high": c + 1.0, "low": c - 1.0, "close": c, "volume": [1e6] * len(c)},
        index=pd.date_range(start, periods=len(c), freq="B"),
    )


def _salita(n=80, da=100.0, a=140.0):
    return _bars(np.linspace(da, a, n))


@pytest.fixture
def stato_1r():
    return {"AAPL": {**ENTERED_10, "stage": "1R_done", "trail_since": "2026-01-01"}}


# --- il livello, in isolamento -------------------------------------------

def test_il_livello_e_massimo_meno_tre_atr():
    bars = _salita()
    livello, valore_atr = bot._trailing_stop_level(bars, "long", None)
    massimo = float(bars["high"].max())
    assert livello == pytest.approx(massimo - bot.TRAIL_ATR_MULT * valore_atr)
    assert livello < massimo


def test_lo_short_e_simmetrico():
    bars = _bars(np.linspace(140.0, 100.0, 80))
    livello, valore_atr = bot._trailing_stop_level(bars, "short", None)
    assert livello == pytest.approx(float(bars["low"].min()) + bot.TRAIL_ATR_MULT * valore_atr)


def test_il_massimo_parte_dalla_data_di_1r_non_dall_entrata():
    """Differenza non cosmetica: un picco PRIMA di 1R non deve alzare lo
    stop, altrimenti si protegge un livello che il titolo non ha piu'
    toccato da quando la posizione e' a mezzo carico."""
    prezzi = list(np.linspace(100, 200, 40)) + list(np.linspace(120, 130, 40))
    bars = _bars(prezzi)
    data_1r = bars.index[40]
    con_picco, _ = bot._trailing_stop_level(bars, "long", None)
    senza_picco, _ = bot._trailing_stop_level(bars, "long", str(data_1r.date()))
    assert senza_picco < con_picco


def test_storico_troppo_corto_non_produce_livelli():
    assert bot._trailing_stop_level(_bars([100, 101, 102]), "long", None) is None
    assert bot._trailing_stop_level(None, "long", None) is None


def test_nessuna_barra_dopo_la_data_di_1r():
    bars = _salita()
    assert bot._trailing_stop_level(bars, "long", "2099-01-01") is None


# --- la regola di movimento ----------------------------------------------

def test_lo_stop_non_torna_mai_indietro():
    """IL test che conta. Uno stop che scende trasforma una protezione in
    una scommessa: ogni giorno di ribasso allargherebbe la perdita
    massima accettata."""
    assert bot._trail_improves("long", 110.0, 100.0, 2.0) is True
    assert bot._trail_improves("long", 90.0, 100.0, 2.0) is False
    assert bot._trail_improves("long", 100.0, 100.0, 2.0) is False
    assert bot._trail_improves("short", 90.0, 100.0, 2.0) is True
    assert bot._trail_improves("short", 110.0, 100.0, 2.0) is False


def test_la_soglia_di_movimento_e_configurabile_ma_di_default_e_zero(monkeypatch):
    """Di default lo stop si sposta a ogni miglioramento, come e' stato
    misurato: il trailing gira solo a mercato chiuso, quindi la finestra
    fra cancellazione e reinvio non ha prezzo. La soglia resta disponibile
    in configurazione, e quando c'e' deve essere rispettata."""
    from common import config as cfg
    assert cfg.SHORT_TERM_TRAILING_MIN_MOVE_ATR == 0.0
    monkeypatch.setattr(bot, "TRAIL_MIN_MOVE_ATR", 0.25)
    margine = 0.25 * 2.0
    assert bot._trail_improves("long", 100.0 + margine * 0.5, 100.0, 2.0) is False
    assert bot._trail_improves("long", 100.0 + margine * 1.5, 100.0, 2.0) is True


def test_il_trailing_e_acceso_di_default():
    """La misura ha superato in campione E fuori campione: l'interruttore
    e' acceso. Se questo test fallisce, qualcuno ha spento una funzione
    validata senza passare da una nuova misura."""
    from common import config as cfg
    assert cfg.SHORT_TERM_TRAILING_ATR_MULT == 3.0


# --- dentro il ciclo giornaliero -----------------------------------------

def _cicla(broker, stato, bars):
    with patch("bot.get_daily_bars", return_value=bars), _patched_state(stato) as s:
        bot.manage_open_short_term_positions(broker)
        return s


def test_dopo_1r_lo_stop_sale_col_massimo(stato_1r):
    broker = _broker([_position("AAPL", 5, 100.0, 138.0)], open_orders=[_order("limit"), _order("stop")])
    s = _cicla(broker, stato_1r, _salita())

    assert broker.submit_stop.called or broker.submit_oco_exit.called
    nuovo = s.data["AAPL"]["trail_stop"]
    assert nuovo > 100.0, "lo stop e' rimasto al pareggio invece di salire"
    assert nuovo < 138.0, "lo stop e' sopra il prezzo: chiuderebbe subito la posizione"


def test_a_mercato_aperto_non_si_tocca_niente(stato_1r):
    """Il massimo di una giornata in corso non e' il massimo della
    giornata. Uno stop alzato su un massimo provvisorio non si puo'
    riabbassare quando il titolo scende nel pomeriggio."""
    broker = _broker([_position("AAPL", 5, 100.0, 138.0)], open_orders=[_order("limit"), _order("stop")])
    broker.is_market_open.return_value = True

    s = _cicla(broker, stato_1r, _salita())

    assert "trail_stop" not in s.data["AAPL"]
    broker.cancel_open_orders.assert_not_called()


def test_prima_di_1r_non_si_trascina_niente():
    """Prima di 1R lo stop e' quello che detta il grafico e non si tocca:
    e' l'unica cosa che definisce quanto si rischia sull'operazione."""
    broker = _broker([_position("AAPL", 10, 100.0, 103.0)], open_orders=[_order("limit"), _order("stop")])
    s = _cicla(broker, {"AAPL": dict(ENTERED_10)}, _salita())
    assert "trail_stop" not in s.data["AAPL"]


def test_uno_stop_gia_oltre_il_prezzo_non_viene_inviato(stato_1r):
    """Dopo un crollo il Chandelier puo' cadere sopra il prezzo corrente:
    inviarlo sarebbe una vendita a mercato immediata, cioe' un'uscita non
    voluta travestita da protezione."""
    prezzi = list(np.linspace(100, 200, 60)) + [120.0] * 20
    broker = _broker([_position("AAPL", 5, 100.0, 120.0)], open_orders=[_order("limit"), _order("stop")])
    s = _cicla(broker, stato_1r, _bars(prezzi))
    assert "trail_stop" not in s.data["AAPL"]
    broker.cancel_open_orders.assert_not_called()


def test_se_il_reinvio_fallisce_lo_stato_non_dice_che_siamo_protetti(stato_1r):
    """Il ciclo dopo deve ritrovare lo stop vecchio e riprovare, invece di
    credere di proteggere a un livello che al broker non esiste."""
    broker = _broker([_position("AAPL", 5, 100.0, 138.0)], open_orders=[_order("limit"), _order("stop")])
    broker.submit_oco_exit.side_effect = RuntimeError("broker giu'")
    broker.submit_stop.side_effect = RuntimeError("broker giu'")

    with patch("bot.get_daily_bars", return_value=_salita()), \
         patch("bot._fallback_protect") as ripiego, \
         _patched_state(stato_1r) as s:
        bot.manage_open_short_term_positions(broker)

    assert ripiego.called, "la posizione e' rimasta scoperta senza ripiego"
    assert "trail_stop" not in s.data["AAPL"]


def test_uno_stato_vecchio_senza_trail_since_non_rompe_il_ciclo(stato_1r):
    """Chi aggiorna il bot ha posizioni aperte con uno stato scritto dalla
    versione precedente: non deve esplodere, deve solo essere prudente."""
    del stato_1r["AAPL"]["trail_since"]
    broker = _broker([_position("AAPL", 5, 100.0, 138.0)], open_orders=[_order("limit"), _order("stop")])
    s = _cicla(broker, stato_1r, _salita())
    assert s.data["AAPL"].get("trail_stop", 100.0) >= 100.0


def test_il_runner_dopo_3r_viene_trascinato_anche_lui():
    broker = _broker([_position("AAPL", 2, 100.0, 138.0)], open_orders=[_order("stop")])
    stato = {"AAPL": {**ENTERED_10, "stage": "3R_done", "trail_since": "2026-01-01"}}
    s = _cicla(broker, stato, _salita())
    assert s.data["AAPL"].get("trail_stop", 0) > 100.0
