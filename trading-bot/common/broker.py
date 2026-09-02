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

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass, AssetExchange, AssetStatus, OrderClass, OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import (
    GetAssetsRequest,
    GetOrdersRequest,
    MarketOrderRequest,
    StopLossRequest,
    StopOrderRequest,
)

from common import config

log = logging.getLogger("bot")

# Borse "principali" per il full-market scan: esclude OTC (penny stock/
# scarsa trasparenza) e le sedi non-equity (crypto, ecc.).
_ALLOWED_EXCHANGES = {AssetExchange.NYSE, AssetExchange.NASDAQ, AssetExchange.ARCA, AssetExchange.AMEX, AssetExchange.BATS}


class Broker:
    def __init__(self) -> None:
        config.require_alpaca_keys()
        self.client = TradingClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY, paper=config.ALPACA_PAPER)
        self.data_client = StockHistoricalDataClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY)
        if not config.ALPACA_PAPER:
            log.warning("ALPACA_PAPER=false -- this bot will trade with REAL MONEY.")

    def is_market_open(self) -> bool:
        return bool(self.client.get_clock().is_open)

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
        """Tutti i titoli azionari USA effettivamente negoziabili su Alpaca
        (NYSE/NASDAQ/ARCA/AMEX/BATS), esclusi OTC e simboli non "semplici"
        (warrant/unit/azioni privilegiate hanno suffissi non alfabetici) --
        sostituisce la watchlist fissa quando SHORT_TERM_USE_FULL_MARKET=true."""
        request = GetAssetsRequest(asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE)
        assets = self.client.get_all_assets(request)
        symbols = [
            a.symbol
            for a in assets
            if a.tradable and a.exchange in _ALLOWED_EXCHANGES and a.symbol.isalpha() and len(a.symbol) <= 5
        ]
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
                snapshots = self.data_client.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=chunk))
            except Exception as exc:
                log.warning("Liquidity snapshot fallito per il batch che inizia con %s: %s", chunk[0], exc)
                continue
            for symbol, snap in snapshots.items():
                bar = getattr(snap, "daily_bar", None)
                if bar is None or bar.close is None or bar.volume is None:
                    continue
                result[symbol] = {"price": float(bar.close), "dollar_volume": float(bar.close) * float(bar.volume)}
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
                request = StockBarsRequest(symbol_or_symbols=chunk, timeframe=TimeFrame.Day, start=start, end=end)
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

    def _open_stop_orders(self, symbol: str) -> list:
        request = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
        orders = self.client.get_orders(request)
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

    def place_stop(self, symbol: str, qty: float, stop_price: float, side: str):
        """Nuovo ordine stop GTC per la quantita' indicata, dopo aver
        cancellato gli stop gia' aperti sul titolo (mai due stop attivi
        sulla stessa posizione)."""
        if qty <= 0:
            return None
        self.cancel_open_stop_orders(symbol)
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
