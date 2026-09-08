"""Notifiche e log: sono il modo in cui il bot dice che qualcosa non va.

Un guasto qui non fa perdere soldi da solo, ma rende invisibili tutti gli
altri -- ed e' il motivo per cui in questo progetto ogni percorso di
"rinuncia" manda un avviso invece di limitarsi a un log."""
import json
import logging
import urllib.error

import pytest

from common import config, logger_setup, notify


# --- notifiche ----------------------------------------------------------------

def test_without_a_webhook_nothing_is_sent(monkeypatch):
    monkeypatch.setattr(config, "ALERT_WEBHOOK_URL", "")
    sent = []
    monkeypatch.setattr(notify.urllib.request, "urlopen", lambda *a, **k: sent.append(a))

    notify.alert("qualcosa e' andato storto", level="error")

    assert sent == []


def test_the_message_carries_the_level_and_the_text(monkeypatch):
    monkeypatch.setattr(config, "ALERT_WEBHOOK_URL", "https://esempio.invalid/hook")
    captured = {}

    def _urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode())
        captured["method"] = request.get_method()
        captured["timeout"] = timeout

    monkeypatch.setattr(notify.urllib.request, "urlopen", _urlopen)

    notify.alert("AAPL: posizione SCOPERTA", level="error")

    assert captured["url"] == "https://esempio.invalid/hook"
    assert captured["method"] == "POST"
    assert "AAPL: posizione SCOPERTA" in captured["body"]["text"]
    assert captured["timeout"] == 10          # mai appeso a tempo indeterminato


@pytest.mark.parametrize("level,marker", [("info", "ℹ️"), ("warning", "⚠️"), ("error", "🚨")])
def test_each_level_has_its_own_marker(monkeypatch, level, marker):
    monkeypatch.setattr(config, "ALERT_WEBHOOK_URL", "https://esempio.invalid/hook")
    body = {}
    monkeypatch.setattr(
        notify.urllib.request, "urlopen",
        lambda request, timeout=None: body.update(json.loads(request.data.decode())),
    )

    notify.alert("messaggio", level=level)

    assert body["text"].startswith(marker)


def test_a_dead_notification_service_never_stops_the_trading_cycle(monkeypatch, caplog):
    """La promessa di alert() e' "non solleva mai": un problema con il
    servizio di notifica non deve far fallire il ciclo che lo sta usando."""
    monkeypatch.setattr(config, "ALERT_WEBHOOK_URL", "https://esempio.invalid/hook")

    def _boom(*a, **k):
        raise urllib.error.URLError("servizio irraggiungibile")

    monkeypatch.setattr(notify.urllib.request, "urlopen", _boom)

    with caplog.at_level(logging.WARNING):
        notify.alert("messaggio")          # non deve sollevare

    assert "Notifica webhook fallita" in caplog.text


def test_a_malformed_webhook_url_does_not_raise_either(monkeypatch, caplog):
    """Un URL storto in .env fa sollevare gia' alla costruzione della
    richiesta, PRIMA di urlopen: per questo tutto sta dentro il try."""
    monkeypatch.setattr(config, "ALERT_WEBHOOK_URL", "non-e-un-url")

    with caplog.at_level(logging.WARNING):
        notify.alert("messaggio")

    assert "Notifica webhook fallita" in caplog.text


# --- log ----------------------------------------------------------------------

def test_logging_writes_a_rotating_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = logging.getLogger()
    previous = root.handlers[:]
    root.handlers = []
    try:
        logger_setup.setup_logging()
        kinds = {type(h).__name__ for h in root.handlers}
        assert "RotatingFileHandler" in kinds
        assert (tmp_path / "logs").is_dir()
        rotating = next(h for h in root.handlers if type(h).__name__ == "RotatingFileHandler")
        assert rotating.maxBytes > 0 and rotating.backupCount > 0
    finally:
        for h in root.handlers:
            h.close()
        root.handlers = previous


def test_an_unwritable_log_folder_does_not_stop_the_bot(tmp_path, monkeypatch, capsys):
    """Il file di log e' un extra. Se la cartella non e' scrivibile (volume
    Docker montato con un altro utente) il bot deve continuare a girare
    loggando su stdout, non morire all'avvio per un permesso."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(logger_setup.os, "makedirs", lambda *a, **k: (_ for _ in ()).throw(PermissionError("negato")))
    root = logging.getLogger()
    previous = root.handlers[:]
    root.handlers = []
    try:
        logger_setup.setup_logging()
        assert {type(h).__name__ for h in root.handlers} == {"StreamHandler"}
        assert "impossibile scrivere" in capsys.readouterr().out.lower()
    finally:
        root.handlers = previous


def test_yfinance_noise_is_turned_down():
    """yfinance logga come ERROR i 404 su dati che per certi strumenti non
    esistono (il calendario trimestrali di un ETF). Con l'universo
    full-market ne arrivano a decine per ciclo, tutti innocui, e
    nasconderebbero gli errori veri."""
    root = logging.getLogger()
    previous = root.handlers[:]
    root.handlers = []
    try:
        logger_setup.setup_logging()
        assert logging.getLogger("yfinance").level >= logging.CRITICAL
    finally:
        for h in root.handlers:
            h.close()
        root.handlers = previous
