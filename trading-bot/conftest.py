# Presence of this file makes pytest add trading-bot/ to sys.path, so
# `from common import config`, `from long_term import ...` and
# `from short_term import ...` resolve regardless of how pytest is invoked.
import pytest
import yfinance


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    """Nessun test tocca la rete.

    Non e' pignoleria: un test che dimentica di sostituire una chiamata a
    yfinance non fallisce, ASPETTA -- il timeout della rete, per ogni
    titolo. E' gia' successo: un solo test dimenticato ha portato la suite
    da 1 a 33 secondi, e su una macchina con la rete disponibile sarebbe
    invece passato leggendo dati veri, cioe' con un esito diverso ogni
    giorno. Qui la chiamata dimenticata fallisce subito e dice quale e'.
    """
    def _blocked(*args, **kwargs):
        raise AssertionError(
            "Chiamata di rete a yfinance dentro un test: va sostituita "
            "(monkeypatch su get_daily_bars / get_daily_bars_batch / yf.Ticker)."
        )

    monkeypatch.setattr(yfinance, "download", _blocked)
    monkeypatch.setattr(yfinance, "Ticker", _blocked)
