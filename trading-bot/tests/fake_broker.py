"""Broker finto che riproduce le regole di Alpaca che contano per questo bot.

Non e' un mock "che dice sempre di si": rifiuta come rifiuterebbe Alpaca.
La regola centrale, quella che ha gia' causato bug veri, e' che un ordine
di VENDITA aperto riserva le azioni: qualunque altra vendita sulle stesse
azioni viene respinta finche' il primo non e' cancellato."""
import itertools
from dataclasses import dataclass, field


class Rejected(Exception):
    """Equivalente di alpaca.common.exceptions.APIError."""


_ids = itertools.count(1)


@dataclass
class Order:
    symbol: str
    qty: int
    side: str            # buy | sell
    type: str            # stop | limit | market
    stop_price: float | None = None
    limit_price: float | None = None
    oco_group: int | None = None
    child_stop: float | None = None   # gamba stop-loss di un OTO
    id: str = field(default_factory=lambda: f"ord-{next(_ids)}")
    legs: list | None = None


@dataclass
class Position:
    symbol: str
    qty: int
    avg_entry_price: float
    current_price: float


class FakeBroker:
    def __init__(self, cash=100_000.0, trading_day=True, market_open=False):
        self.cash = cash
        self.positions: dict[str, Position] = {}
        self.orders: list[Order] = []
        self.trading_day = trading_day
        self.market_open = market_open
        self.rejections: list[str] = []
        self.fail_next_cancel = False
        self.fail_next_submit = False
        self.fail_next_read = False
        self.last_prices: dict[str, float] = {}

    # --- lettura -----------------------------------------------------------
    def is_trading_day(self, day): return self.trading_day
    def is_market_open(self): return self.market_open
    def get_cash(self): return self.cash
    def get_equity(self):
        return self.cash + sum(p.qty * p.current_price for p in self.positions.values())

    def list_open_positions(self):
        return [{"symbol": p.symbol, "qty": float(p.qty), "avg_entry_price": p.avg_entry_price,
                 "current_price": p.current_price} for p in self.positions.values()]

    def open_entry_symbols(self):
        return {o.symbol for o in self.orders if o.side == "buy"}

    def get_open_position(self, symbol):
        p = self.positions.get(symbol)
        if p is None: return None
        return {"symbol": p.symbol, "qty": float(p.qty), "avg_entry_price": p.avg_entry_price,
                "current_price": p.current_price}

    def list_open_orders(self, symbol):
        if self.fail_next_read:
            self.fail_next_read = False
            raise RuntimeError("errore di rete leggendo gli ordini")
        return [o for o in self.orders if o.symbol == symbol]

    # --- quantita' riservate (la regola che conta) --------------------------
    def _reserved_sell_qty(self, symbol):
        """Le due gambe di un OCO sono alternative: Alpaca riserva le azioni
        UNA volta sola, non due. Contarle due volte faceva sembrare che il
        bot sovra-impegnasse le azioni quando non lo faceva."""
        total, counted_groups = 0, set()
        for o in self.orders:
            if o.symbol != symbol or o.side != "sell":
                continue
            if o.oco_group is not None:
                if o.oco_group in counted_groups:
                    continue
                counted_groups.add(o.oco_group)
            total += o.qty
        return total

    def _check_sell_capacity(self, symbol, qty):
        held = self.positions[symbol].qty if symbol in self.positions else 0
        if self._reserved_sell_qty(symbol) + qty > held:
            self.rejections.append(f"{symbol}: insufficient qty available")
            raise Rejected(f"insufficient qty available for {symbol}")

    # --- scrittura ----------------------------------------------------------
    def cancel_open_orders(self, symbol):
        if self.fail_next_cancel:
            self.fail_next_cancel = False
            raise RuntimeError(f"{symbol}: cancellazione rifiutata")
        n = len(self.list_open_orders(symbol))
        self.orders = [o for o in self.orders if o.symbol != symbol]
        return n

    def cancel_open_stop_orders(self, symbol):
        if self.fail_next_cancel:
            self.fail_next_cancel = False
            raise RuntimeError(f"{symbol}: cancellazione stop rifiutata")
        keep = [o for o in self.orders if not (o.symbol == symbol and o.type == "stop")]
        n = len(self.orders) - len(keep)
        self.orders = keep
        return n

    def submit_stop_entry(self, symbol, qty, side, entry_price, stop_price):
        if qty <= 0: return None
        if any(o.symbol == symbol and o.side == "buy" for o in self.orders):
            self.rejections.append(f"{symbol}: DUE ordini d'ingresso")
        o = Order(symbol, qty, "buy", "stop", stop_price=entry_price, child_stop=stop_price)
        self.orders.append(o)
        return o

    def submit_oco_exit(self, symbol, qty, side, limit_price, stop_price):
        if qty <= 0: return None
        if self.fail_next_submit:
            self.fail_next_submit = False
            raise Rejected(f"{symbol}: OCO rifiutato dal broker")
        self._check_sell_capacity(symbol, qty)
        g = next(_ids)
        limit = Order(symbol, qty, "sell", "limit", limit_price=limit_price, oco_group=g)
        stop = Order(symbol, qty, "sell", "stop", stop_price=stop_price, oco_group=g)
        limit.legs = [stop]
        self.orders += [limit, stop]
        return limit

    def submit_stop(self, symbol, qty, stop_price, side):
        if qty <= 0: return None
        self._check_sell_capacity(symbol, qty)
        o = Order(symbol, int(qty), "sell", "stop", stop_price=stop_price)
        self.orders.append(o)
        return o

    def flatten(self, symbol):
        self.cancel_open_stop_orders(symbol)
        self.orders = [o for o in self.orders if o.symbol != symbol]
        p = self.positions.pop(symbol, None)
        if p: self.cash += p.qty * p.current_price
        return p

    def buy_market(self, symbol, qty):
        """Acquisto a mercato: usato dal lungo termine (Harry Browne,
        Advanced). Muove davvero cassa e posizioni, altrimenti un test che
        lo esercita non proverebbe nulla."""
        if qty <= 0: return None
        if self.fail_next_submit:
            self.fail_next_submit = False
            raise Rejected(f"{symbol}: acquisto rifiutato")
        price = self.last_prices.get(symbol, 100.0)
        cost = qty * price
        if cost > self.cash:
            self.rejections.append(f"{symbol}: cassa insufficiente")
            raise Rejected(f"{symbol}: insufficient buying power")
        self.cash -= cost
        pos = self.positions.get(symbol)
        if pos is None:
            self.positions[symbol] = Position(symbol, int(qty), price, price)
        else:
            pos.avg_entry_price = (pos.avg_entry_price * pos.qty + cost) / (pos.qty + qty)
            pos.qty += int(qty)
        return True

    def sell_market(self, symbol, qty):
        if qty <= 0: return None
        if self.fail_next_submit:
            self.fail_next_submit = False
            raise Rejected(f"{symbol}: vendita rifiutata")
        pos = self.positions.get(symbol)
        if pos is None or qty > pos.qty:
            self.rejections.append(f"{symbol}: vendita oltre le azioni possedute")
            raise Rejected(f"{symbol}: insufficient qty available")
        price = self.last_prices.get(symbol, pos.current_price)
        pos.qty -= int(qty)
        self.cash += qty * price
        if pos.qty <= 0: del self.positions[symbol]
        return True

    # --- simulazione del mercato -------------------------------------------
    def advance(self, prices: dict[str, float]):
        """Un giorno di mercato: esegue gli ordini toccati dal prezzo."""
        for sym, price in prices.items():
            for o in list(self.orders):
                if o.symbol != sym: continue
                if o.side == "buy" and o.type == "stop" and price >= o.stop_price:
                    self.orders.remove(o)
                    self.positions[sym] = Position(sym, o.qty, o.stop_price, price)
                    self.cash -= o.qty * o.stop_price
                    if o.child_stop is not None:      # gamba OTO che si attiva
                        self.orders.append(Order(sym, o.qty, "sell", "stop", stop_price=o.child_stop))
                elif o.side == "sell" and sym in self.positions:
                    hit = (o.type == "stop" and price <= o.stop_price) or \
                          (o.type == "limit" and price >= o.limit_price)
                    if hit:
                        self.orders.remove(o)
                        for other in [x for x in self.orders if x.oco_group is not None and x.oco_group == o.oco_group]:
                            self.orders.remove(other)          # l'altra gamba dell'OCO decade
                        pos = self.positions[sym]
                        sold = min(o.qty, pos.qty)
                        pos.qty -= sold
                        self.cash += sold * price
                        if pos.qty <= 0:
                            del self.positions[sym]
                            self.orders = [x for x in self.orders if x.symbol != sym]
                            break
        self.last_prices.update(prices)
        for sym, price in prices.items():
            if sym in self.positions: self.positions[sym].current_price = price
