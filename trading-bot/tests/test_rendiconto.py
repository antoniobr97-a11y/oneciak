"""Ricostruzione delle operazioni chiuse dagli ordini eseguiti.

Il rischio di questo codice non e' che si rompa: e' che produca numeri
plausibili e sbagliati, e che noi ci costruiamo sopra delle decisioni. Il
caso che conta di piu' e' la scala di uscita del corso (meta' a 1R, 30% a
3R, il resto che corre): sono tre eseguiti per UN solo ingresso, e
contarli come tre operazioni gonfierebbe la percentuale di successo.
"""
from datetime import datetime, timedelta

import pytest

from short_term.rendiconto import ricostruisci, statistiche

GIORNO = datetime(2026, 9, 1)


def _fill(symbol, side, qty, price, giorno=0, stop=None):
    return {
        "symbol": symbol, "side": side, "qty": qty, "price": price,
        "filled_at": GIORNO + timedelta(days=giorno),
        "type": "stop" if stop else "market", "stop_price": stop,
    }


def test_un_giro_completo_e_una_operazione():
    fills = [_fill("AAPL", "buy", 10, 100.0), _fill("AAPL", "sell", 10, 110.0, giorno=5)]

    (op,) = ricostruisci(fills)

    assert op.qty == 10
    assert op.prezzo_ingresso == 100.0
    assert op.prezzo_uscita == 110.0
    assert op.pnl == pytest.approx(100.0)
    assert op.vinta
    assert op.giorni == 5


def test_la_scala_del_corso_conta_come_UNA_operazione():
    """IL test. Tre uscite su un solo ingresso: una decisione, un
    risultato. Contarle come tre darebbe due 'vittorie' per un ingresso."""
    fills = [
        _fill("MSFT", "buy", 100, 50.0),
        _fill("MSFT", "sell", 50, 55.0, giorno=3),    # 1R
        _fill("MSFT", "sell", 30, 65.0, giorno=10),   # 3R
        _fill("MSFT", "sell", 20, 70.0, giorno=30),   # runner
    ]

    operazioni = ricostruisci(fills)

    assert len(operazioni) == 1
    op = operazioni[0]
    assert op.uscite == 3
    assert op.qty == 100
    # 50*55 + 30*65 + 20*70 = 2750 + 1950 + 1400 = 6100, speso 5000
    assert op.pnl == pytest.approx(1100.0)


def test_due_giri_sullo_stesso_titolo_sono_due_operazioni():
    fills = [
        _fill("KO", "buy", 10, 40.0, giorno=0),
        _fill("KO", "sell", 10, 44.0, giorno=4),
        _fill("KO", "buy", 20, 45.0, giorno=20),
        _fill("KO", "sell", 20, 43.0, giorno=25),
    ]

    prima, seconda = ricostruisci(fills)

    assert prima.pnl == pytest.approx(40.0)
    assert seconda.pnl == pytest.approx(-40.0)
    assert seconda.vinta is False


def test_una_posizione_ancora_aperta_non_compare():
    """Il rendiconto e' delle operazioni CHIUSE: una a meta' non ha
    ancora un risultato, e metterla dentro falserebbe la media."""
    fills = [_fill("NVDA", "buy", 10, 100.0), _fill("NVDA", "sell", 4, 120.0, giorno=2)]

    assert ricostruisci(fills) == []


def test_gli_etf_del_lungo_termine_si_escludono():
    """Li' i 'buy' sono ribilanciamenti trimestrali, non operazioni con un
    ingresso e un'uscita: mescolarli falserebbe ogni statistica."""
    fills = [
        _fill("GLD", "buy", 10, 400.0), _fill("GLD", "sell", 10, 410.0, giorno=90),
        _fill("AAPL", "buy", 10, 100.0), _fill("AAPL", "sell", 10, 110.0, giorno=5),
    ]

    operazioni = ricostruisci(fills, escludi={"GLD", "TLT", "SHY", "VT"})

    assert [o.symbol for o in operazioni] == ["AAPL"]


def test_il_risultato_in_R_usa_lo_stop_iniziale():
    """+2R vuol dire "ha guadagnato due volte quello che rischiava"."""
    fills = [
        _fill("AMD", "buy", 10, 100.0),
        _fill("AMD", "sell", 10, 120.0, giorno=7, stop=90.0),  # rischiava 10, ha fatto 20
    ]

    (op,) = ricostruisci(fills)

    assert op.erre == pytest.approx(2.0)


def test_senza_stop_il_risultato_in_R_resta_ignoto():
    """Meglio dire "non lo so" che inventare un numero su cui poi si
    prendono decisioni."""
    fills = [_fill("AMD", "buy", 10, 100.0), _fill("AMD", "sell", 10, 120.0, giorno=7)]

    (op,) = ricostruisci(fills)

    assert op.erre is None


def test_le_statistiche_sui_numeri_che_contano():
    fills = [
        _fill("A", "buy", 10, 100.0, giorno=0), _fill("A", "sell", 10, 130.0, giorno=10),
        _fill("B", "buy", 10, 100.0, giorno=0), _fill("B", "sell", 10, 90.0, giorno=2),
        _fill("C", "buy", 10, 100.0, giorno=0), _fill("C", "sell", 10, 90.0, giorno=2),
    ]

    s = statistiche(ricostruisci(fills))

    assert s["totale"] == 3
    assert s["vinte"] == 1 and s["perse"] == 2
    assert s["percentuale_successo"] == pytest.approx(33.33, abs=0.01)
    assert s["pnl_totale"] == pytest.approx(100.0)
    assert s["profit_factor"] == pytest.approx(1.5)   # 300 incassati / 200 persi


def test_senza_operazioni_non_si_inventano_statistiche():
    assert statistiche([]) == {"totale": 0}


# --- il comando da riga di comando ----------------------------------------

def test_il_comando_gira_con_operazioni_vere(capsys):
    import argparse
    from unittest.mock import MagicMock, patch

    import bot

    broker = MagicMock()
    broker.list_filled_orders.return_value = [
        _fill("AAPL", "buy", 10, 100.0), _fill("AAPL", "sell", 10, 110.0, giorno=5, stop=95.0),
        _fill("GLD", "buy", 5, 400.0), _fill("GLD", "sell", 5, 410.0, giorno=90),
    ]

    with patch.object(bot, "Broker", return_value=broker):
        bot.cmd_rendiconto(argparse.Namespace(ultime=20))

    uscita = capsys.readouterr().out
    assert "AAPL" in uscita
    assert "GLD" not in uscita, "gli ETF di lungo termine non vanno nel rendiconto del breve"
    assert "POCHE" in uscita, "con poche operazioni va detto che i numeri non bastano"


def test_il_comando_non_si_rompe_senza_operazioni(capsys):
    import argparse
    from unittest.mock import MagicMock, patch

    import bot

    broker = MagicMock()
    broker.list_filled_orders.return_value = []

    with patch.object(bot, "Broker", return_value=broker):
        bot.cmd_rendiconto(argparse.Namespace(ultime=20))

    assert "Nessuna operazione ancora chiusa" in capsys.readouterr().out
