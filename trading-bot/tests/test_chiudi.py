"""Comando `chiudi`: esce a mercato da una posizione aperta.

Le azioni sono trattenute dallo stop-loss, quindi per vendere bisogna
prima cancellarlo. Fra il "cancella" e il "vendi" la posizione e'
SCOPERTA: il pericolo di questo comando e' tutto li'. A mercato aperto
dura il tempo di un ordine a mercato; a mercato chiuso durerebbe una
notte intera, ed e' il caso che i test qui sotto presidiano.
"""
import argparse
from unittest.mock import MagicMock, patch

import bot
from tests.test_bot import _order, _patched_state


def _args(symbol="BITO", execute=False):
    return argparse.Namespace(symbol=symbol, execute=execute)


def _broker_finto(posizione=None, ordini=(), mercato_aperto=True):
    b = MagicMock()
    b.get_open_position.return_value = posizione
    b.list_open_orders.return_value = list(ordini)
    b.cancel_open_orders.return_value = len(ordini)
    b.is_market_open.return_value = mercato_aperto
    return b


def test_a_mercato_chiuso_si_rifiuta():
    """IL test. Togliere lo stop la sera lascerebbe la posizione scoperta
    fino all'apertura dopo, perche' l'ordine di vendita resta in coda."""
    broker = _broker_finto(
        posizione={"symbol": "BITO", "qty": 1, "current_price": 10.26},
        ordini=[_order("stop")],
        mercato_aperto=False,
    )

    with patch("bot.Broker", return_value=broker), _patched_state({"BITO": {"stage": "entered"}}) as stato:
        bot.cmd_chiudi(_args("BITO", execute=True))

    broker.cancel_open_orders.assert_not_called()
    broker.sell_market.assert_not_called()
    assert "BITO" in stato.data, "lo stato e' stato cancellato senza aver chiuso niente"


def test_senza_execute_non_tocca_niente():
    broker = _broker_finto(posizione={"symbol": "BITO", "qty": 1}, ordini=[_order("stop")])

    with patch("bot.Broker", return_value=broker), _patched_state():
        bot.cmd_chiudi(_args("BITO", execute=False))

    broker.cancel_open_orders.assert_not_called()
    broker.sell_market.assert_not_called()


def test_prima_toglie_la_protezione_poi_vende():
    """L'ordine conta: vendere con lo stop ancora aperto viene rifiutato
    dal broker per "insufficient qty" (le azioni sono riservate)."""
    broker = _broker_finto(posizione={"symbol": "BITO", "qty": 3}, ordini=[_order("stop")])
    sequenza = []
    broker.cancel_open_orders.side_effect = lambda s: sequenza.append("cancella") or 1
    broker.sell_market.side_effect = lambda s, q: sequenza.append(f"vendi {q}")

    with patch("bot.Broker", return_value=broker), _patched_state({"BITO": {"stage": "entered"}}) as stato:
        bot.cmd_chiudi(_args("BITO", execute=True))

    assert sequenza == ["cancella", "vendi 3"]
    assert "BITO" not in stato.data


def test_una_posizione_short_si_chiude_comprando():
    broker = _broker_finto(posizione={"symbol": "XYZ", "qty": -5}, ordini=[_order("stop")])

    with patch("bot.Broker", return_value=broker), _patched_state():
        bot.cmd_chiudi(_args("XYZ", execute=True))

    broker.buy_market.assert_called_once_with("XYZ", 5)
    broker.sell_market.assert_not_called()


def test_senza_posizione_non_fa_niente():
    """Qui serve `annulla`, non `chiudi`: il messaggio lo dice."""
    broker = _broker_finto(posizione=None)

    with patch("bot.Broker", return_value=broker), _patched_state():
        bot.cmd_chiudi(_args("PIPPO", execute=True))

    broker.cancel_open_orders.assert_not_called()
    broker.sell_market.assert_not_called()


def test_frazione_di_azione_non_si_vende_a_mercato():
    """Alpaca accetta le frazioni solo su alcuni ordini. Si tolgono comunque
    gli ordini di protezione, ma non si manda una vendita di 0 azioni."""
    broker = _broker_finto(posizione={"symbol": "BITO", "qty": 0.4}, ordini=[_order("stop")])

    with patch("bot.Broker", return_value=broker), _patched_state():
        bot.cmd_chiudi(_args("BITO", execute=True))

    broker.sell_market.assert_not_called()
