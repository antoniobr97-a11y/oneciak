from unittest.mock import MagicMock, patch

import pytest
import requests

from alpaca.common.exceptions import APIError

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


def test_flatten_cancels_open_stops_before_closing(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [_stop_order("a"), _stop_order("b")])

    broker.flatten("AAPL")

    names = [c[0] for c in client.method_calls if c[0] in ("cancel_order_by_id", "close_position")]
    assert names == ["cancel_order_by_id", "cancel_order_by_id", "close_position"]


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
    client.submit_order.side_effect = [APIError("order class not supported for stop"), MagicMock(id="x")]

    broker.submit_stop_entry("AAPL", 10, "long", 101.5, 95.0)

    assert client.submit_order.call_count == 2
    fallback = client.submit_order.call_args_list[1][0][0]
    assert fallback.stop_price == 101.5 and fallback.stop_loss is None


def test_submit_stop_entry_never_resends_after_a_network_error(monkeypatch):
    """Un errore di rete non dice che l'ordine NON e' stato creato: la POST
    puo' essere arrivata comunque. Reinviarla piazzerebbe un SECONDO ordine
    d'ingresso sullo stesso titolo -- doppia posizione, doppio rischio."""
    broker, client = _broker_with_client(monkeypatch, [])
    client.submit_order.side_effect = [
        requests.exceptions.ConnectionError("connessione persa"),
        MagicMock(id="ordine-doppio"),
    ]

    with pytest.raises(requests.exceptions.ConnectionError):
        broker.submit_stop_entry("AAPL", 10, "long", 101.5, 95.0)

    assert client.submit_order.call_count == 1


def test_submit_stop_entry_reraises_an_invalid_level_without_retrying(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [])
    client.submit_order.side_effect = APIError("stop price must be greater than current price")

    with pytest.raises(APIError):
        broker.submit_stop_entry("AAPL", 10, "long", 101.5, 95.0)

    assert client.submit_order.call_count == 1


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

    # emittenti piu' recenti di prodotti a leva su singolo titolo
    assert _is_leveraged_or_inverse("GraniteShares 2x Long NVDA Daily ETF")
    assert _is_leveraged_or_inverse("T-Rex 2X Long Tesla Daily Target ETF")
    assert _is_leveraged_or_inverse("Tradr 2X Long NVDA Daily ETF")
    assert _is_leveraged_or_inverse("MicroSectors FANG+ Index -3X Inverse Leveraged ETN")
    assert _is_leveraged_or_inverse("ProShares Ultra S&P500")
    assert _is_leveraged_or_inverse("ProShares Short VIX Short-Term Futures ETF")

    # Il moltiplicatore da solo deve bastare: non tutti i prodotti a leva
    # nominano un emittente noto o una parola direzionale.
    assert _is_leveraged_or_inverse("Bitcoin 2X Strategy ETF")
    assert _is_leveraged_or_inverse("Some Index 1.5X Fund")
    assert _is_leveraged_or_inverse("Something -1X ETN")

    # ammessi: azioni e ETF normali, compresi obbligazionari e oro
    assert not _is_leveraged_or_inverse("Apple Inc. Common Stock")
    assert not _is_leveraged_or_inverse("SPDR S&P 500 ETF Trust")
    assert not _is_leveraged_or_inverse("iShares 20+ Year Treasury Bond ETF")
    assert not _is_leveraged_or_inverse("SPDR Gold Shares")
    assert not _is_leveraged_or_inverse("Vanguard Total Stock Market ETF")


def test_real_stocks_are_not_mistaken_for_leveraged_products():
    """Un titolo escluso qui non viene MAI analizzato e non compare in
    nessun log: e' una perdita di opportunita' invisibile. La versione a
    sottostringhe libere buttava fuori sei di questi nomi reali."""
    from common.broker import _is_leveraged_or_inverse

    for name in (
        "Ultragenyx Pharmaceutical Inc.",   # conteneva "ULTRA"
        "Ultra Clean Holdings, Inc.",       # "Ultra" come parola, ma non e' un ETF
        "Ultralife Corporation",            # conteneva "ULTRA"
        "Ultratech Inc",                    # conteneva "ULTRA"
        "RBC Bearings Incorporated",        # "BEARings"
        "Daily Journal Corporation",        # "Daily" come parola, nessun emittente a leva
        "Bullfrog AI Holdings, Inc.",       # "BULLfrog"
        "Short Squeeze Inc",                # "Short" come parola, nessun emittente a leva
        "10x Genomics, Inc.",               # il moltiplicatore e' limitato a 1-4x
        "Longboard Pharmaceuticals, Inc.",  # "LONGboard"
        "Bear Creek Mining Corporation",    # "Bear" come parola, nessun emittente a leva
        "Apple Inc.",
        "NVIDIA Corporation",
        # Nomi che coincidono con emittenti di prodotti a leva ma non hanno
        # nessuna parola direzionale: l'emittente da solo non deve bastare.
        "Trex Company, Inc.",
        "MaxLinear, Inc.",
        "MAXIMUS, Inc.",
    ):
        assert not _is_leveraged_or_inverse(name), f"{name} escluso per errore dall'universo"


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

    assert broker.cancel_open_stop_orders("AAPL") == 1
    client.cancel_order_by_id.assert_called_once_with("stop-1")


def test_limit_orders_are_not_mistaken_for_stops(monkeypatch):
    """cancel_open_stop_orders non deve toccare il limit di presa di
    profitto: cancellarlo lascerebbe la posizione senza uscita in guadagno."""
    broker, client = _broker_with_client(monkeypatch, [_stop_order("lim-1", kind="limit")])

    assert broker.cancel_open_stop_orders("AAPL") == 0
    client.cancel_order_by_id.assert_not_called()


def test_missing_position_is_none_but_a_broker_failure_is_raised(monkeypatch):
    """None vuol dire "non ho quella posizione". Se lo dicesse anche su un
    errore di rete, il ciclo aprirebbe una SECONDA posizione su un titolo
    che ha gia' -- o ricomprerebbe un ETF di lungo termine gia' in
    portafoglio."""
    from alpaca.common.exceptions import APIError

    monkeypatch.setattr(config, "ALPACA_API_KEY", "test_key")
    monkeypatch.setattr(config, "ALPACA_SECRET_KEY", "test_secret")
    broker = Broker()
    broker.client = MagicMock()

    broker.client.get_open_position.side_effect = APIError('{"code":40410000,"message":"position does not exist"}')
    assert broker.get_open_position("AAPL") is None

    broker.client.get_open_position.side_effect = requests.exceptions.ConnectTimeout("rete assente")
    with pytest.raises(requests.exceptions.ConnectTimeout):
        broker.get_open_position("AAPL")

    # Anche un errore del broker che ARRIVA come APIError, ma non e' un
    # "questa posizione non esiste": solo il 404 significa "non ce l'ho".
    broker.client.get_open_position.side_effect = APIError('{"code":50010000,"message":"internal server error"}')
    with pytest.raises(APIError):
        broker.get_open_position("AAPL")


def test_flatten_raises_instead_of_pretending_the_position_is_closed(monkeypatch):
    """flatten cancella gli stop PRIMA di chiudere. Ingoiando l'errore, il
    chiamante proseguiva come se fosse chiusa: cancellava lo stato e
    lasciava al broker una posizione aperta, senza stop e senza piu' i
    dati per gestirla."""
    broker, client = _broker_with_client(monkeypatch, [_stop_order()])
    client.close_position.side_effect = RuntimeError("chiusura rifiutata")

    with pytest.raises(RuntimeError):
        broker.flatten("AAPL")


def test_a_failed_cancellation_raises_instead_of_being_only_logged(monkeypatch):
    """Chi chiama cancella per rimpiazzare. Con il vecchio ordine ancora
    vivo si finisce con DUE ordini d'ingresso sullo stesso titolo: se
    scattano entrambi si compra il doppio e si rischia il doppio."""
    broker, client = _broker_with_client(monkeypatch, [_stop_order("a"), _stop_order("b")])
    client.cancel_order_by_id.side_effect = [None, RuntimeError("rifiutato")]

    with pytest.raises(RuntimeError):
        broker.cancel_open_orders("AAPL")

    assert client.cancel_order_by_id.call_count == 2  # le tenta comunque tutte


def test_a_failed_stop_cancellation_raises(monkeypatch):
    broker, client = _broker_with_client(monkeypatch, [_stop_order()])
    client.cancel_order_by_id.side_effect = RuntimeError("rifiutato")

    with pytest.raises(RuntimeError):
        broker.cancel_open_stop_orders("AAPL")


# --- ordini a mercato (li usa il lungo termine) -------------------------------

def test_market_buy_and_sell_shape(monkeypatch):
    """Sono gli ordini con cui il lungo termine compra e vende davvero:
    lato giusto, quantita' giusta, validita' giornaliera."""
    broker, client = _broker_with_client(monkeypatch, [])

    broker.buy_market("VTI", 12)
    order = client.submit_order.call_args[0][0]
    assert order.symbol == "VTI" and order.qty == 12
    assert str(order.side).lower().endswith("buy")
    assert str(order.time_in_force).lower().endswith("day")

    broker.sell_market("VTI", 5)
    order = client.submit_order.call_args[0][0]
    assert str(order.side).lower().endswith("sell") and order.qty == 5


def test_market_orders_of_zero_or_less_are_not_sent(monkeypatch):
    """Un ribilanciamento che calcola 0 quote non deve mandare niente al
    broker: sarebbe un ordine rifiutato per nulla."""
    broker, client = _broker_with_client(monkeypatch, [])

    assert broker.buy_market("VTI", 0) is None
    assert broker.sell_market("VTI", -3) is None
    client.submit_order.assert_not_called()
