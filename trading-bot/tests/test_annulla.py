"""Comando `annulla`: toglie un ordine d'ingresso ancora in attesa.

Il pericolo di un comando del genere non e' che non funzioni: e' che
funzioni TROPPO. Su un titolo gia' in portafoglio "annullare gli ordini"
non annulla un ingresso -- cancella lo stop-loss e la presa di profitto, e
lascia la posizione scoperta. Il primo test e' quello.
"""
import argparse
from unittest.mock import MagicMock, patch

import bot
from tests.test_bot import _order, _patched_state


def _args(symbol="IBIT", execute=False):
    return argparse.Namespace(symbol=symbol, execute=execute)


def _broker_finto(posizione=None, ordini=()):
    b = MagicMock()
    b.get_open_position.return_value = posizione
    b.list_open_orders.return_value = list(ordini)
    b.cancel_open_orders.return_value = len(ordini)
    return b


def test_su_una_posizione_APERTA_si_rifiuta():
    """IL test. Cancellare qui toglierebbe la protezione, non un ingresso."""
    broker = _broker_finto(posizione={"symbol": "AAPL", "qty": 10})

    with patch("bot.Broker", return_value=broker), _patched_state({"AAPL": {"stage": "entered"}}) as stato:
        bot.cmd_annulla(_args("AAPL", execute=True))

    broker.cancel_open_orders.assert_not_called()
    assert "AAPL" in stato.data, "lo stato e' stato cancellato su una posizione aperta"


def test_senza_execute_non_cancella_niente():
    broker = _broker_finto(ordini=[_order("stop")])
    with patch("bot.Broker", return_value=broker), _patched_state():
        bot.cmd_annulla(_args(execute=False))
    broker.cancel_open_orders.assert_not_called()


def test_con_execute_annulla_e_libera_il_titolo():
    broker = _broker_finto(ordini=[_order("stop")])
    with patch("bot.Broker", return_value=broker), \
         patch("bot.notify.alert"), \
         _patched_state({"IBIT": {"stage": "pending"}}) as stato:
        bot.cmd_annulla(_args(execute=True))

    broker.cancel_open_orders.assert_called_once_with("IBIT")
    assert "IBIT" not in stato.data, "lo stato pendente e' rimasto dopo l'annullamento"


def test_nessun_ordine_pulisce_lo_stato_orfano():
    """Stato che dice 'pendente' ma al broker non c'e' niente: si allinea."""
    broker = _broker_finto(ordini=[])
    with patch("bot.Broker", return_value=broker), _patched_state({"IBIT": {"stage": "pending"}}) as stato:
        bot.cmd_annulla(_args(execute=True))
    broker.cancel_open_orders.assert_not_called()
    assert "IBIT" not in stato.data


def test_il_simbolo_e_case_insensitive():
    broker = _broker_finto(ordini=[_order("stop")])
    with patch("bot.Broker", return_value=broker), patch("bot.notify.alert"), _patched_state():
        bot.cmd_annulla(_args("ibit", execute=True))
    broker.get_open_position.assert_called_once_with("IBIT")
