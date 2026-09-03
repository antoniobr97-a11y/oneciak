from unittest.mock import MagicMock, patch

import pytest
import requests

from common import config
from common.broker import Broker


class _FakeBar:
    def __init__(self, close):
        self.close = close


class _FakeBarSet(dict):
    def __getitem__(self, symbol):
        return dict.__getitem__(self, symbol)


class _FakeDataClient:
    def __init__(self, bars_by_symbol):
        self._bars_by_symbol = bars_by_symbol

    def get_stock_bars(self, request):
        requested = set(request.symbol_or_symbols)
        return _FakeBarSet({s: self._bars_by_symbol[s] for s in requested if s in self._bars_by_symbol})


def _make_broker(monkeypatch, bars_by_symbol):
    monkeypatch.setattr(config, "ALPACA_API_KEY", "test_key")
    monkeypatch.setattr(config, "ALPACA_SECRET_KEY", "test_secret")
    broker = Broker()
    broker.data_client = _FakeDataClient(bars_by_symbol)
    return broker


def test_volatility_snapshot_computes_annualized_stdev(monkeypatch):
    # Rendimenti giornalieri costanti +1% -> deviazione standard 0 -> vol 0.
    closes = [100.0]
    for _ in range(10):
        closes.append(closes[-1] * 1.01)
    broker = _make_broker(monkeypatch, {"FLAT": [_FakeBar(c) for c in closes]})

    result = broker.volatility_snapshot(["FLAT"])

    assert result["FLAT"] == pytest.approx(0.0, abs=1e-9)


def test_volatility_snapshot_higher_for_more_volatile_series(monkeypatch):
    calm = [100.0, 101.0, 100.0, 101.0, 100.0, 101.0, 100.0]
    wild = [100.0, 120.0, 90.0, 130.0, 80.0, 140.0, 70.0]
    broker = _make_broker(
        monkeypatch,
        {"CALM": [_FakeBar(c) for c in calm], "WILD": [_FakeBar(c) for c in wild]},
    )

    result = broker.volatility_snapshot(["CALM", "WILD"])

    assert result["WILD"] > result["CALM"]


def test_volatility_snapshot_skips_symbols_with_too_few_bars(monkeypatch):
    broker = _make_broker(monkeypatch, {"THIN": [_FakeBar(100.0), _FakeBar(101.0)]})

    result = broker.volatility_snapshot(["THIN"])

    assert "THIN" not in result


def test_volatility_snapshot_skips_symbols_missing_from_response(monkeypatch):
    broker = _make_broker(monkeypatch, {})

    result = broker.volatility_snapshot(["MISSING"])

    assert result == {}


# --- audit: ordine delle operazioni sugli stop ---------------------------------

def _stop_order(order_id="stop-1", kind="stop", deprecated_field_only=False):
    """Ordine come lo restituisce Alpaca: `type` e `order_type` (deprecato)
    portano lo stesso valore. Con deprecated_field_only si simula la forma
    in cui `type` non e' valorizzato."""
    o = MagicMock()
    o.id = order_id
    o.type = None if deprecated_field_only else kind
    o.order_type = kind
    return o


def _broker_with_client(monkeypatch, open_orders):
    monkeypatch.setattr(config, "ALPACA_API_KEY", "test_key")
    monkeypatch.setattr(config, "ALPACA_SECRET_KEY", "test_secret")
    broker = Broker()
    client = MagicMock()
    client.get_orders.return_value = open_orders
    broker.client = client
    return broker, client


def test_close_partial_cancels_open_stop_before_submitting(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [_stop_order()])

    broker.close_partial("AAPL", 5, "long")

    names = [c[0] for c in client.method_calls if c[0] in ("cancel_order_by_id", "submit_order")]
    assert names == ["cancel_order_by_id", "submit_order"]


def test_flatten_cancels_open_stops_before_closing(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [_stop_order("a"), _stop_order("b")])

    broker.flatten("AAPL")

    names = [c[0] for c in client.method_calls if c[0] in ("cancel_order_by_id", "close_position")]
    assert names == ["cancel_order_by_id", "cancel_order_by_id", "close_position"]


def test_place_stop_replaces_existing_stop_with_gtc(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [_stop_order()])

    broker.place_stop("AAPL", 5, 100.0, "long")

    client.cancel_order_by_id.assert_called_once_with("stop-1")
    submitted = client.submit_order.call_args[0][0]
    assert str(submitted.time_in_force).lower().endswith("gtc")
    assert submitted.qty == 5 and submitted.stop_price == 100.0


def test_enter_with_stop_uses_gtc_so_the_stop_leg_survives_the_day(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [])

    broker.enter_with_stop("AAPL", 10, "long", 95.0)

    submitted = client.submit_order.call_args[0][0]
    assert str(submitted.time_in_force).lower().endswith("gtc")
    assert submitted.stop_loss.stop_price == 95.0


# --- corso, video 41: ingresso buy-stop con stop-loss attaccato, uscite OCO ----

def test_submit_stop_entry_is_a_gtc_stop_order_with_oto_stop_loss(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [])

    broker.submit_stop_entry("AAPL", 10, "long", 101.5, 95.0)

    submitted = client.submit_order.call_args[0][0]
    assert submitted.stop_price == 101.5
    assert str(submitted.side).lower().endswith("buy")
    assert str(submitted.time_in_force).lower().endswith("gtc")
    assert str(submitted.order_class).lower().endswith("oto")
    assert submitted.stop_loss.stop_price == 95.0


def test_submit_stop_entry_falls_back_to_plain_stop_if_oto_rejected(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [])
    client.submit_order.side_effect = [ValueError("order class not supported for stop"), MagicMock(id="x")]

    broker.submit_stop_entry("AAPL", 10, "long", 101.5, 95.0)

    assert client.submit_order.call_count == 2
    fallback = client.submit_order.call_args_list[1][0][0]
    assert fallback.stop_price == 101.5 and fallback.stop_loss is None


def test_submit_stop_entry_short_uses_sell_side(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [])

    broker.submit_stop_entry("TSLA", 10, "short", 98.5, 105.0)

    submitted = client.submit_order.call_args[0][0]
    assert str(submitted.side).lower().endswith("sell")
    assert submitted.stop_loss.stop_price == 105.0


def test_submit_oco_exit_shape(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [])

    broker.submit_oco_exit("AAPL", 5, "long", 105.0, 95.0)

    submitted = client.submit_order.call_args[0][0]
    assert str(submitted.order_class).lower().endswith("oco")
    assert str(submitted.side).lower().endswith("sell")
    assert submitted.limit_price == 105.0
    assert submitted.take_profit.limit_price == 105.0
    assert submitted.stop_loss.stop_price == 95.0
    assert str(submitted.time_in_force).lower().endswith("gtc")


def test_cancel_open_orders_cancels_every_open_order(monkeypatch):
    limit = MagicMock(); limit.id = "lim"; limit.order_type = "limit"
    broker, client = _broker_with_client(monkeypatch, [_stop_order("a"), limit])

    assert broker.cancel_open_orders("AAPL") == 2
    assert [c[0][0] for c in client.cancel_order_by_id.call_args_list] == ["a", "lim"]


def test_leveraged_and_inverse_products_are_recognised():
    from common.broker import _is_leveraged_or_inverse

    # esclusi: introdurrebbero leva 2-3x per via indiretta
    assert _is_leveraged_or_inverse("ProShares UltraPro QQQ")
    assert _is_leveraged_or_inverse("Direxion Daily Semiconductor Bull 3X Shares")
    assert _is_leveraged_or_inverse("ProShares Short S&P500")
    assert _is_leveraged_or_inverse("ProShares UltraShort 20+ Year Treasury")
    assert _is_leveraged_or_inverse("Direxion Daily Financial Bear 3X")

    # ammessi: azioni e ETF normali, compresi obbligazionari e oro
    assert not _is_leveraged_or_inverse("Apple Inc. Common Stock")
    assert not _is_leveraged_or_inverse("SPDR S&P 500 ETF Trust")
    assert not _is_leveraged_or_inverse("iShares 20+ Year Treasury Bond ETF")
    assert not _is_leveraged_or_inverse("SPDR Gold Shares")
    assert not _is_leveraged_or_inverse("Vanguard Total Stock Market ETF")


def test_list_tradable_symbols_includes_etfs_and_drops_leveraged(monkeypatch):
    from alpaca.trading.enums import AssetExchange

    def _asset(symbol, name, exchange=AssetExchange.NASDAQ, tradable=True):
        a = MagicMock()
        a.symbol, a.name, a.exchange, a.tradable = symbol, name, exchange, tradable
        return a

    broker, client = _broker_with_client(monkeypatch, [])
    client.get_all_assets.return_value = [
        _asset("AAPL", "Apple Inc. Common Stock"),
        _asset("SPY", "SPDR S&P 500 ETF Trust", AssetExchange.ARCA),
        _asset("TLT", "iShares 20+ Year Treasury Bond ETF", AssetExchange.NASDAQ),
        _asset("TQQQ", "ProShares UltraPro QQQ"),                       # a leva -> fuori
        _asset("SQQQ", "ProShares UltraPro Short QQQ"),                 # inverso -> fuori
        _asset("OTCX", "Some OTC Thing", AssetExchange.OTC),            # OTC -> fuori
        _asset("NOPE", "Untradable Inc", tradable=False),               # non negoziabile -> fuori
    ]

    assert broker.list_tradable_symbols() == ["AAPL", "SPY", "TLT"]


def test_submit_stop_does_not_cancel_other_orders(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [_stop_order("keep")])

    broker.submit_stop("AAPL", 5, 95.0, "long")

    client.cancel_order_by_id.assert_not_called()
    submitted = client.submit_order.call_args[0][0]
    assert submitted.stop_price == 95.0 and submitted.qty == 5


# --- Robustezza di rete ---------------------------------------------------
# Regressione: al primo avvio reale su PC di casa il bot e' partito prima
# che la connessione fosse pronta e un ConnectTimeout su /v2/calendar ha
# fatto fallire l'intero ciclo giornaliero. alpaca-py non ritenta gli
# errori di connessione e non imposta timeout.

def test_harden_session_retries_connection_errors():
    from common.broker import HTTP_CONNECT_RETRIES, _harden_session

    class _Client:
        _session = requests.Session()

    client = _Client()
    _harden_session(client)

    retry = client._session.get_adapter("https://paper-api.alpaca.markets").max_retries
    assert retry.connect == HTTP_CONNECT_RETRIES
    assert retry.backoff_factor > 0


def test_resilient_session_sends_a_default_timeout():
    """alpaca-py chiama request() senza timeout: senza un default una
    connessione appesa blocca il bot invece di fallire e riprovare."""
    from common.broker import HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT, _ResilientSession

    session = _ResilientSession()
    with patch.object(requests.Session, "request", return_value="ok") as sent:
        session.request("GET", "https://example.invalid")
    assert sent.call_args.kwargs["timeout"] == (HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT)


def test_resilient_session_keeps_an_explicit_timeout():
    from common.broker import _ResilientSession

    session = _ResilientSession()
    with patch.object(requests.Session, "request", return_value="ok") as sent:
        session.request("GET", "https://example.invalid", timeout=5)
    assert sent.call_args.kwargs["timeout"] == 5


def test_harden_session_never_retries_a_post_on_a_read_error():
    """Un ordine e' un POST: se la richiesta e' partita ma la risposta non
    arriva, ripeterla alla cieca puo' creare un secondo ordine. urllib3
    ritenta gli errori di lettura solo sui metodi idempotenti."""
    from common.broker import _harden_session

    class _Client:
        _session = requests.Session()

    client = _Client()
    _harden_session(client)
    retry = client._session.get_adapter("https://paper-api.alpaca.markets").max_retries
    assert "POST" not in retry.allowed_methods
    assert "GET" in retry.allowed_methods


def test_harden_session_is_a_no_op_when_the_client_has_no_requests_session():
    from common.broker import _harden_session

    class _Client:
        _session = object()

    client = _Client()
    sentinel = client._session
    _harden_session(client)
    assert client._session is sentinel


def test_order_type_is_read_from_either_field():
    """alpaca-py espone `type` e `order_type` (deprecato) e a seconda della
    forma dell'ordine uno dei due puo' essere vuoto. Leggerne uno solo
    significherebbe, in silenzio, non riconoscere uno stop da cancellare
    prima di una vendita -- che il broker poi rifiuterebbe."""
    from common.broker import order_type_name

    assert order_type_name(_stop_order()) == "stop"
    assert order_type_name(_stop_order(deprecated_field_only=True)) == "stop"
    assert order_type_name(_stop_order(kind="limit")) == "limit"
    assert order_type_name(object()) == ""


def test_open_stop_orders_found_via_the_deprecated_field(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [_stop_order(deprecated_field_only=True)])

    broker.place_stop("AAPL", 5, 100.0, "long")

    client.cancel_order_by_id.assert_called_once_with("stop-1")


def test_limit_orders_are_not_mistaken_for_stops(monkeypatch):
    """cancel_open_stop_orders non deve toccare il limit di presa di
    profitto: cancellarlo lascerebbe la posizione senza uscita in guadagno."""
    broker, client = _broker_with_client(monkeypatch, [_stop_order("lim-1", kind="limit")])

    assert broker.cancel_open_stop_orders("AAPL") == 0
    client.cancel_order_by_id.assert_not_called()
