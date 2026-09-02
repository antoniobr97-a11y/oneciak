"""Thin wrapper around Alpaca's trading API (paper by default -- see
config.ALPACA_PAPER / .env).

Covers what both strategies need:
  - account/position lookups, market-hours check
  - long_term: plain market buy/sell for periodic rebalancing
  - short_term: entry + stop-loss order (OTO, no fixed take-profit -- the
    target is managed dynamically, see short_term/levels.py) and the
    follow-up management calls (partial close at 1R, stop moved to
    breakeven) described in STRATEGY.md 2.4
"""
import logging
import math
import statistics
from datetime import datetime, timedelta, timezone

from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass, AssetExchange, AssetStatus, OrderClass, OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import (
    GetAssetsRequest,
    GetCalendarRequest,
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    StopLossRequest,
    StopOrderRequest,
    TakeProfitRequest,
)

from common import config

log = logging.getLogger("bot")

# Borse "principali" per il full-market scan: esclude OTC (penny stock/
# scarsa trasparenza) e le sedi non-equity (crypto, ecc.).
_ALLOWED_EXCHANGES = {AssetExchange.NYSE, AssetExchange.NASDAQ, AssetExchange.ARCA, AssetExchange.AMEX, AssetExchange.BATS}

# ETF a leva (2x/3x) e inversi: superano facilmente il filtro di volatilita'
# proprio perche' amplificano i movimenti, quindi il bot li sceglierebbe
# spesso -- ma comprarli rischiando l'1% significa avere leva 2-3 sul
# mercato per via indiretta, cioe' esattamente il rischio che la strategia
# esclude (nessuna leva, vedi STRATEGY.md). In piu' il decadimento
# giornaliero li rende inadatti a posizioni tenute settimane. Alpaca non
# ha un flag per identificarli: si riconoscono dal nome del prodotto.
_LEVERAGED_NAME_MARKERS = (
    "2X", "3X", "-1X", "1.5X", "ULTRA", "ULTRASHORT", "ULTRAPRO",
    "LEVERAGED", "INVERSE", "BEAR", "BULL ", " BULL", "SHORT ", "DAILY ",
)


def _data_feed() -> DataFeed:
    """Canale dati configurato (default IEX, incluso negli account gratuiti).
    Senza specificarlo Alpaca usa SIP e rifiuta i dati recenti a chi non ha
    l'abbonamento -- vedi config.ALPACA_DATA_FEED."""
    try:
        return DataFeed(config.ALPACA_DATA_FEED)
    except ValueError:
        log.warning("ALPACA_DATA_FEED=%r non valido, uso 'iex'.", config.ALPACA_DATA_FEED)
        return DataFeed.IEX


def _is_leveraged_or_inverse(name: str) -> bool:
    upper = f" {name.upper()} "
    return any(marker in upper for marker in _LEVERAGED_NAME_MARKERS)


class Broker:
    def __init__(self) -> None:
        config.require_alpaca_keys()
        self.client = TradingClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY, paper=config.ALPACA_PAPER)
        self.data_client = StockHistoricalDataClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY)
        if not config.ALPACA_PAPER:
            log.warning("ALPACA_PAPER=false -- this bot will trade with REAL MONEY.")

    def is_market_open(self) -> bool:
        return bool(self.client.get_clock().is_open)

    def is_trading_day(self, day) -> bool:
        """Vero se in quella data la borsa USA ha (o ha avuto) una seduta --
        falso su weekend e festivi. Serve al ciclo di breve termine, che gira
        DOPO la chiusura: "mercato aperto adesso" sarebbe sempre falso a
        quell'ora, ma il giorno di borsa c'e' stato e le sue barre sono
        definitive."""
        days = self.client.get_calendar(GetCalendarRequest(start=day, end=day))
        return len(days) > 0

    def get_equity(self) -> float:
        return float(self.client.get_account().equity)

    def get_cash(self) -> float:
        """Cassa disponibile (non il buying power a margine): usata per
        limitare la size delle nuove posizioni al capitale davvero
        disponibile, senza leva -- stessa assunzione del backtest storico
        (STRATEGY.md), che senza questo tetto mostrava una leva impossibile."""
        return float(self.client.get_account().cash)

    def get_open_position_qty(self, symbol: str) -> float:
        try:
            pos = self.client.get_open_position(symbol)
            return float(pos.qty)
        except Exception:
            return 0.0

    def get_open_position(self, symbol: str) -> dict | None:
        try:
            pos = self.client.get_open_position(symbol)
        except Exception:
            return None
        return {
            "symbol": pos.symbol,
            "qty": float(pos.qty),
            "avg_entry_price": float(pos.avg_entry_price),
            "current_price": float(pos.current_price) if pos.current_price else None,
        }

    def list_open_positions(self) -> list[dict]:
        return [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price) if p.current_price else None,
            }
            for p in self.client.get_all_positions()
        ]

    # --- short_term: universo full-market (invece della watchlist statica) --

    def list_tradable_symbols(self) -> list[str]:
        """Tutto il mercato USA negoziabile su Alpaca (NYSE/NASDAQ/ARCA/
        AMEX/BATS): azioni **e** ETF, inclusi obbligazionari, oro, settoriali
        -- Alpaca li classifica tutti come us_equity. Esclusi: OTC, simboli
        non "semplici" (warrant/unit/privilegiate hanno suffissi non
        alfabetici) e i prodotti a LEVA o inversi (vedi
        _is_leveraged_or_inverse). Sostituisce la watchlist fissa quando
        SHORT_TERM_USE_FULL_MARKET=true."""
        request = GetAssetsRequest(asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE)
        assets = self.client.get_all_assets(request)
        symbols = [
            a.symbol
            for a in assets
            if a.tradable
            and a.exchange in _ALLOWED_EXCHANGES
            and a.symbol.isalpha()
            and len(a.symbol) <= 5
            and not _is_leveraged_or_inverse(getattr(a, "name", "") or "")
        ]
        excluded = sum(
            1 for a in assets
            if a.tradable and a.exchange in _ALLOWED_EXCHANGES and _is_leveraged_or_inverse(getattr(a, "name", "") or "")
        )
        log.info("Universo Alpaca: %d strumenti negoziabili (esclusi %d a leva/inversi).", len(symbols), excluded)
        return sorted(set(symbols))

    def liquidity_snapshot(self, symbols: list[str], batch_size: int = 200) -> dict[str, dict]:
        """Prezzo e volume$ approssimato (ultima barra giornaliera, feed IEX
        gratuito -- una frazione del volume USA reale, ma sufficiente per un
        ranking di liquidità relativo) per ogni simbolo, usato per il
        prefiltro veloce prima della pipeline completa (STRATEGY.md "Step 1:
        screening", vedi build_full_market_universe in short_term/screener.py)."""
        result: dict[str, dict] = {}
        for i in range(0, len(symbols), batch_size):
            chunk = symbols[i : i + batch_size]
            try:
                snapshots = self.data_client.get_stock_snapshot(
                    StockSnapshotRequest(symbol_or_symbols=chunk, feed=_data_feed())
                )
            except Exception as exc:
                log.warning("Liquidity snapshot fallito per il batch che inizia con %s: %s", chunk[0], exc)
                continue
            for symbol, snap in snapshots.items():
                bar = getattr(snap, "daily_bar", None)
                if bar is None or bar.close is None or bar.volume is None:
                    continue
                result[symbol] = {
                    "price": float(bar.close),
                    "volume": float(bar.volume),
                    "dollar_volume": float(bar.close) * float(bar.volume),
                }
        return result

    def volatility_snapshot(self, symbols: list[str], lookback_days: int = 30, batch_size: int = 200) -> dict[str, float]:
        """Volatilità storica annualizzata (deviazione standard dei
        rendimenti giornalieri, feed IEX) sugli ultimi `lookback_days`
        giorni di borsa per ogni simbolo. Il backtest storico (STRATEGY.md
        "v4") ha mostrato che un prefiltro di sola liquidità lascia passare
        titoli difensivi a bassa volatilità (utility, beni di consumo) su
        cui un sistema trend-following rende peggio -- questo prefiltro
        aggiuntivo li esclude prima della pipeline completa."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=lookback_days * 2)  # margine per weekend/festivi
        result: dict[str, float] = {}
        for i in range(0, len(symbols), batch_size):
            chunk = symbols[i : i + batch_size]
            try:
                request = StockBarsRequest(
                    symbol_or_symbols=chunk, timeframe=TimeFrame.Day, start=start, end=end, feed=_data_feed()
                )
                bars = self.data_client.get_stock_bars(request)
            except Exception as exc:
                log.warning("Volatility snapshot fallito per il batch che inizia con %s: %s", chunk[0], exc)
                continue
            for symbol in chunk:
                try:
                    symbol_bars = bars[symbol]
                except KeyError:
                    continue
                closes = [b.close for b in symbol_bars if b.close is not None]
                if len(closes) < 5:
                    continue
                returns = [closes[j] / closes[j - 1] - 1 for j in range(1, len(closes))]
                result[symbol] = statistics.pstdev(returns) * math.sqrt(252)
        return result

    # --- long_term: plain rebalancing orders -------------------------------

    def buy_market(self, symbol: str, qty: int):
        if qty <= 0:
            return None
        order = MarketOrderRequest(symbol=symbol, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
        result = self.client.submit_order(order)
        log.info("BUY (market) submitted: %s qty=%s order_id=%s", symbol, qty, result.id)
        return result

    def sell_market(self, symbol: str, qty: int):
        if qty <= 0:
            return None
        order = MarketOrderRequest(symbol=symbol, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.DAY)
        result = self.client.submit_order(order)
        log.info("SELL (market) submitted: %s qty=%s order_id=%s", symbol, qty, result.id)
        return result

    # --- short_term: entry + stop, then dynamic management -----------------

    def enter_with_stop(self, symbol: str, qty: int, side: str, stop_price: float):
        """Market entry with an attached stop-loss (OTO order). No fixed
        take-profit: STRATEGY.md 2.4 manages the exit dynamically (partial
        close at 1R, stop moved to breakeven, let the rest run)."""
        if qty <= 0:
            log.info("Skipping %s: computed position size is 0.", symbol)
            return None

        order_side = OrderSide.BUY if side == "long" else OrderSide.SELL
        # GTC, non DAY: la gamba stop-loss dell'ordine OTO eredita il
        # time-in-force del padre. Con DAY lo stop scadeva a fine giornata
        # (il bot entra alle 15:50, 10 minuti prima della chiusura),
        # lasciando la posizione SENZA protezione da tutti i giorni
        # successivi -- bug trovato nell'audit, vedi STRATEGY.md.
        order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.GTC,
            order_class=OrderClass.OTO,
            stop_loss=StopLossRequest(stop_price=round(stop_price, 2)),
        )
        result = self.client.submit_order(order)
        log.info(
            "%s entry submitted: %s qty=%s stop=%.2f order_id=%s",
            side.upper(), symbol, qty, stop_price, result.id,
        )
        return result

    # --- short_term: ingresso con ordine stop + uscite con limit/stop (corso,
    # video 41/44: long = buy stop in entrata, sell limit a T1, sell stop di
    # protezione) --------------------------------------------------------------

    def list_open_orders(self, symbol: str) -> list:
        request = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
        return list(self.client.get_orders(request))

    def cancel_open_orders(self, symbol: str) -> int:
        """Cancella TUTTI gli ordini aperti sul titolo (entrata pendente,
        stop di protezione, limit di take-profit). Ritorna quanti."""
        cancelled = 0
        for order in self.list_open_orders(symbol):
            try:
                self.client.cancel_order_by_id(order.id)
                cancelled += 1
            except Exception as exc:
                log.warning("Could not cancel order %s for %s: %s", order.id, symbol, exc)
        return cancelled

    def submit_stop_entry(self, symbol: str, qty: int, side: str, entry_price: float, stop_price: float):
        """Ordine di INGRESSO stop GTC al livello calcolato (chiusura della
        barra di setup + volatilita'), come da corso: si entra solo se il
        prezzo supera davvero il livello, non a mercato alla chiusura.
        Prova ad attaccare lo stop-loss come gamba OTO; se il broker non
        accetta un padre di tipo stop per l'OTO, invia lo stop d'ingresso
        da solo e lo stop-loss viene messo dal ciclo successivo
        (auto-riparazione in bot.py) -- finestra scoperta al massimo di una
        seduta, segnalata nel log."""
        if qty <= 0:
            return None
        order_side = OrderSide.BUY if side == "long" else OrderSide.SELL
        request = StopOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.GTC,
            stop_price=round(entry_price, 2),
            order_class=OrderClass.OTO,
            stop_loss=StopLossRequest(stop_price=round(stop_price, 2)),
        )
        try:
            result = self.client.submit_order(request)
        except Exception as exc:
            log.warning("OTO con padre stop rifiutato per %s (%s): invio lo stop d'ingresso senza gamba stop-loss.", symbol, exc)
            request = StopOrderRequest(
                symbol=symbol, qty=qty, side=order_side, time_in_force=TimeInForce.GTC, stop_price=round(entry_price, 2)
            )
            result = self.client.submit_order(request)
        log.info(
            "%s STOP entry submitted: %s qty=%s entry=%.2f stop=%.2f order_id=%s",
            side.upper(), symbol, qty, entry_price, stop_price, result.id,
        )
        return result

    def submit_oco_exit(self, symbol: str, qty: float, side: str, limit_price: float, stop_price: float):
        """Uscita OCO per una quota della posizione: take-profit limit a
        `limit_price` e stop di protezione a `stop_price`, uno cancella
        l'altro. Alpaca: type=limit, take_profit.limit_price e
        stop_loss.stop_price obbligatori."""
        if qty <= 0:
            return None
        close_side = OrderSide.SELL if side == "long" else OrderSide.BUY
        request = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=close_side,
            time_in_force=TimeInForce.GTC,
            limit_price=round(limit_price, 2),
            order_class=OrderClass.OCO,
            take_profit=TakeProfitRequest(limit_price=round(limit_price, 2)),
            stop_loss=StopLossRequest(stop_price=round(stop_price, 2)),
        )
        result = self.client.submit_order(request)
        log.info("OCO exit submitted: %s qty=%s take_profit=%.2f stop=%.2f order_id=%s", symbol, qty, limit_price, stop_price, result.id)
        return result

    def _open_stop_orders(self, symbol: str) -> list:
        orders = self.list_open_orders(symbol)
        return [o for o in orders if o.order_type is not None and "stop" in str(o.order_type).lower()]

    def get_open_stop_order(self, symbol: str):
        stops = self._open_stop_orders(symbol)
        return stops[0] if stops else None

    def cancel_open_stop_orders(self, symbol: str) -> int:
        """Cancella TUTTI gli stop aperti sul titolo (dopo errori/riemissioni
        potrebbero essercene piu' di uno). Su Alpaca un ordine di vendita
        aperto riserva le azioni: qualunque altra vendita sulle stesse
        azioni (chiusura parziale a 1R/3R, chiusura totale) viene rifiutata
        con "insufficient qty available" finche' lo stop non e' cancellato
        -- bug trovato nell'audit, vedi STRATEGY.md. Ritorna il numero di
        ordini cancellati."""
        cancelled = 0
        for order in self._open_stop_orders(symbol):
            try:
                self.client.cancel_order_by_id(order.id)
                cancelled += 1
            except Exception as exc:
                log.warning("Could not cancel stop order %s for %s: %s", order.id, symbol, exc)
        return cancelled

    def submit_stop(self, symbol: str, qty: float, stop_price: float, side: str):
        """Ordine stop GTC di protezione per la quantita' indicata, SENZA
        toccare gli altri ordini aperti (usato accanto a un OCO su un'altra
        quota della stessa posizione)."""
        if qty <= 0:
            return None
        stop_side = OrderSide.SELL if side == "long" else OrderSide.BUY
        order = StopOrderRequest(
            symbol=symbol,
            qty=qty,
            side=stop_side,
            time_in_force=TimeInForce.GTC,
            stop_price=round(stop_price, 2),
        )
        result = self.client.submit_order(order)
        log.info("Stop placed: %s qty=%s stop=%.2f order_id=%s", symbol, qty, stop_price, result.id)
        return result

    def place_stop(self, symbol: str, qty: float, stop_price: float, side: str):
        """Nuovo ordine stop GTC per la quantita' indicata, dopo aver
        cancellato gli stop gia' aperti sul titolo (mai due stop attivi
        sulla stessa quota)."""
        if qty <= 0:
            return None
        self.cancel_open_stop_orders(symbol)
        return self.submit_stop(symbol, qty, stop_price, side)

    def move_stop_to_breakeven(self, symbol: str, qty: float, entry_price: float, side: str) -> None:
        """Replace the existing stop order (if any) with one at the entry
        price, for the given remaining quantity."""
        self.place_stop(symbol, qty, entry_price, side)

    def close_partial(self, symbol: str, qty: float, side: str):
        """Close part of an open position at market (used for the 1R/3R
        partial exits). Cancella PRIMA gli stop aperti, altrimenti le
        azioni risultano riservate e l'ordine viene rifiutato -- il
        chiamante deve poi riemettere lo stop per la quantita' residua."""
        if qty <= 0:
            return None
        self.cancel_open_stop_orders(symbol)
        close_side = OrderSide.SELL if side == "long" else OrderSide.BUY
        order = MarketOrderRequest(symbol=symbol, qty=qty, side=close_side, time_in_force=TimeInForce.DAY)
        result = self.client.submit_order(order)
        log.info("Partial close submitted: %s qty=%s order_id=%s", symbol, qty, result.id)
        return result

    def flatten(self, symbol: str):
        """Chiude l'intera posizione, cancellando prima gli stop aperti
        (stesso motivo di close_partial: azioni riservate)."""
        try:
            self.cancel_open_stop_orders(symbol)
            result = self.client.close_position(symbol)
            log.info("Position flattened: %s", symbol)
            return result
        except Exception as exc:
            log.warning("Could not close position for %s: %s", symbol, exc)
            return None
