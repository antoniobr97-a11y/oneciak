"""Una configurazione sbagliata non deve spegnere il bot in silenzio.

Diverse impostazioni errate non danno errore: rendono semplicemente
impossibile aprire posizioni, e dal log sembra solo che "oggi non ci siano
occasioni" -- lo stesso modo in cui si sono gia' manifestati due guasti
reali (feed dati SIP negato, dati di volatilita' mancanti).

Nota sui test: ricaricare il modulo ridefinisce anche ConfigError, quindi
la classe catturata prima del reload non e' la stessa sollevata dopo. Si
usa RuntimeError (di cui ConfigError e' sottoclasse) e si verifica il
messaggio, che e' comunque cio' che conta per chi legge l'errore."""
import importlib

import pytest

from common import config


def _reload_expecting_error(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError) as exc:
        importlib.reload(config)
    for key in env:
        monkeypatch.delenv(key)
    importlib.reload(config)  # ripristina lo stato per i test successivi
    return str(exc.value)


def test_italian_number_format_is_rejected_with_a_readable_message(monkeypatch):
    """In italiano si scrive "10.000" per diecimila e "1,5" per uno virgola
    cinque: il primo diventerebbe 10 in silenzio (capitale diviso mille),
    il secondo farebbe uscire un traceback illeggibile all'avvio."""
    message = _reload_expecting_error(monkeypatch, SHORT_TERM_CAPITAL="1,5")
    assert "SHORT_TERM_CAPITAL" in message
    assert "10.000" in message  # il messaggio mostra l'errore tipico


def test_zero_risk_per_trade_is_rejected(monkeypatch):
    message = _reload_expecting_error(monkeypatch, SHORT_TERM_RISK_PER_TRADE_PCT="0")
    assert "SHORT_TERM_RISK_PER_TRADE_PCT" in message


def test_aggregate_cap_below_single_trade_risk_is_rejected(monkeypatch):
    """Non ci sarebbe posto nemmeno per la prima operazione: il bot non
    aprirebbe mai nulla, senza dire perche'."""
    message = _reload_expecting_error(
        monkeypatch, SHORT_TERM_RISK_PER_TRADE_PCT="2", SHORT_TERM_MAX_AGGREGATE_RISK_PCT="1"
    )
    assert "SHORT_TERM_MAX_AGGREGATE_RISK_PCT" in message


def test_malformed_run_time_is_rejected(monkeypatch):
    message = _reload_expecting_error(monkeypatch, RUN_TIME="16.15")
    assert "RUN_TIME" in message


def test_the_shipped_defaults_are_valid():
    """La configurazione con cui il bot esce dalla scatola deve passare la
    validazione: altrimenti non partirebbe affatto."""
    importlib.reload(config)
    assert config.RUN_TIME == "16:15"
    assert config.SHORT_TERM_RISK_PER_TRADE_PCT == 1.0
    assert config.SHORT_TERM_MAX_AGGREGATE_RISK_PCT == 12.0
