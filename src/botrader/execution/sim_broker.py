"""Simulated broker for backtesting and paper trading.

Fills:
- LIMIT orders fill if a bar's range touches the price (low <= price <= high).
- STOP_MARKET (SL) triggers when price crosses stop; we fill at trigger price plus slippage.
- TAKE_PROFIT_MARKET fills when price reaches it; modeled as a limit at TP price.

Fees: `fee_bps` taker fee on every fill. Slippage applied adversely.

This is a single-symbol-per-call broker; the engine drives `on_bar` for each
symbol in a loop. It is NOT a tick-level simulator — bar fills are an
approximation. For SMC strategies entering on limit orders at OBs, the bar-fill
approximation is reasonable because OB prices are pre-known before the bar.
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict

from ..core.types import (
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
    Trade,
)

log = logging.getLogger(__name__)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class SimBroker:
    def __init__(
        self,
        initial_cash: float = 10_000.0,
        fee_bps: float = 4.0,
        slippage_bps: float = 2.0,
    ):
        self._cash: float = initial_cash
        self._fee_bps = fee_bps
        self._slip_bps = slippage_bps
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, Order] = {}
        self._mark: dict[str, float] = {}
        self._realized_pnl: float = 0.0
        # bracket links: entry_id -> [sl_id, tp_id]
        self._brackets: dict[str, list[str]] = defaultdict(list)
        self._reverse_bracket: dict[str, str] = {}  # child -> entry
        # initial risk per position for R-multiple reporting: symbol -> dollars
        self._initial_risk: dict[str, float] = {}
        # trade log (closed round-trips)
        self._trades: list[Trade] = []
        self._open_trade_meta: dict[str, dict] = {}  # symbol -> {entry_ts, entry_price, qty, side}

    # -- Broker protocol ---------------------------------------------------
    def balance(self) -> float:
        return self._cash

    def equity(self) -> float:
        upnl = 0.0
        for sym, pos in self._positions.items():
            mark = self._mark.get(sym, pos.entry_price)
            sign = 1 if pos.side == "long" else -1
            upnl += sign * (mark - pos.entry_price) * pos.qty
        return self._cash + upnl

    def positions(self) -> list[Position]:
        return list(self._positions.values())

    def open_orders(self, symbol: str | None = None) -> list[Order]:
        out = []
        for o in self._orders.values():
            if o.status not in (OrderStatus.NEW, OrderStatus.OPEN):
                continue
            if symbol is None or o.symbol == symbol:
                out.append(o)
        return out

    def realized_pnl(self) -> float:
        return self._realized_pnl

    def mark_price(self, symbol: str) -> float | None:
        return self._mark.get(symbol)

    def trades(self) -> list[Trade]:
        return list(self._trades)

    def place_order(self, order: Order) -> Order:
        if not order.id:
            order.id = _new_id()
        order.status = OrderStatus.OPEN
        self._orders[order.id] = order
        return order

    def cancel_order(self, order_id: str) -> None:
        o = self._orders.get(order_id)
        if o and o.status in (OrderStatus.NEW, OrderStatus.OPEN):
            o.status = OrderStatus.CANCELED

    def cancel_all(self, symbol: str | None = None) -> None:
        for o in list(self._orders.values()):
            if o.status not in (OrderStatus.NEW, OrderStatus.OPEN):
                continue
            if symbol is None or o.symbol == symbol:
                o.status = OrderStatus.CANCELED

    def close_position(self, symbol: str) -> None:
        pos = self._positions.get(symbol)
        if pos is None:
            return
        mark = self._mark.get(symbol, pos.entry_price)
        self._fill_close(symbol, mark, "close_position", ts=0)

    def set_leverage(self, symbol: str, leverage: float) -> None:
        # sim_broker doesn't model margin explicitly; leverage cap enforced by sizing.
        pass

    # -- Bracket helper ----------------------------------------------------
    def submit_bracket(
        self,
        symbol: str,
        side: Side,
        qty: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        client_id: str | None = None,
    ) -> str:
        entry = Order(
            id=_new_id(), symbol=symbol, side=side, type=OrderType.LIMIT,
            qty=qty, price=entry_price, client_id=client_id,
        )
        self.place_order(entry)
        sl = Order(
            id=_new_id(), symbol=symbol, side="short" if side == "long" else "long",
            type=OrderType.STOP_MARKET, qty=qty, price=None, stop_price=stop_loss,
            reduce_only=True, client_id=f"sl-{client_id}" if client_id else None,
        )
        # SL/TP are placed but won't trigger until the entry fills.
        self.place_order(sl)
        tp = Order(
            id=_new_id(), symbol=symbol, side="short" if side == "long" else "long",
            type=OrderType.TAKE_PROFIT_MARKET, qty=qty, price=take_profit,
            stop_price=take_profit, reduce_only=True,
            client_id=f"tp-{client_id}" if client_id else None,
        )
        self.place_order(tp)
        # Hold them inactive until entry fills; gate via _brackets bookkeeping.
        sl.status = OrderStatus.NEW
        tp.status = OrderStatus.NEW
        self._brackets[entry.id] = [sl.id, tp.id]
        self._reverse_bracket[sl.id] = entry.id
        self._reverse_bracket[tp.id] = entry.id
        # initial risk for R-multiple
        self._initial_risk[symbol] = abs(entry_price - stop_loss) * qty
        return entry.id

    # -- Bar tick ---------------------------------------------------------
    def on_bar(
        self,
        symbol: str,
        ts: int,
        open_: float,
        high: float,
        low: float,
        close: float,
    ) -> None:
        self._mark[symbol] = close

        # 1) Try to fill resting LIMIT entries
        for o in list(self._orders.values()):
            if o.symbol != symbol or o.status != OrderStatus.OPEN:
                continue
            if o.type == OrderType.LIMIT and o.price is not None and low <= o.price <= high:
                self._fill_open(o, o.price, ts)

        # 2) Activate brackets for filled entries (move SL/TP from NEW to OPEN)
        for entry_id, child_ids in list(self._brackets.items()):
            entry = self._orders.get(entry_id)
            if entry is None:
                continue
            if entry.status == OrderStatus.FILLED:
                for cid in child_ids:
                    child = self._orders.get(cid)
                    if child and child.status == OrderStatus.NEW:
                        child.status = OrderStatus.OPEN

        # 3) Try to trigger SLs and TPs
        for o in list(self._orders.values()):
            if o.symbol != symbol or o.status != OrderStatus.OPEN:
                continue
            if o.type == OrderType.STOP_MARKET and o.stop_price is not None:
                # SL: trigger if low <= stop <= high (i.e., bar swept the stop)
                triggered = False
                if o.side == "short":  # SL for long position triggers below
                    if low <= o.stop_price:
                        triggered = True
                elif high >= o.stop_price:
                    triggered = True
                if triggered:
                    fill_px = self._slip(o.stop_price, o.side, adverse=True)
                    self._fill_close_via_order(o, fill_px, ts, reason="stop_loss")
                    self._cancel_sibling(o)
            elif o.type == OrderType.TAKE_PROFIT_MARKET and o.price is not None:
                if low <= o.price <= high:
                    fill_px = self._slip(o.price, o.side, adverse=False)
                    self._fill_close_via_order(o, fill_px, ts, reason="take_profit")
                    self._cancel_sibling(o)

    # -- Internals --------------------------------------------------------
    def _slip(self, price: float, side: Side, adverse: bool) -> float:
        """Apply slippage. If adverse and we're selling, fill lower; etc."""
        bps = self._slip_bps / 1e4
        if side == "long":
            return price * (1 + bps if adverse else 1 - bps)
        return price * (1 - bps if adverse else 1 + bps)

    def _apply_fee(self, notional: float) -> float:
        fee = abs(notional) * self._fee_bps / 1e4
        self._cash -= fee
        return fee

    def _fill_open(self, order: Order, price: float, ts: int) -> None:
        notional = price * order.qty
        fee = self._apply_fee(notional)
        order.status = OrderStatus.FILLED
        order.filled_qty = order.qty
        order.avg_fill_price = price
        # apply margin: we use isolated-style accounting — cash reduces by initial margin
        # but here we just track equity through unrealized PnL for simplicity (cross margin).
        existing = self._positions.get(order.symbol)
        if existing is None:
            self._positions[order.symbol] = Position(
                symbol=order.symbol, side=order.side, qty=order.qty,
                entry_price=price, opened_ts=ts,
            )
            self._open_trade_meta[order.symbol] = {
                "entry_ts": ts,
                "entry_price": price,
                "qty": order.qty,
                "side": order.side,
                "fees": fee,
            }
        else:
            # increasing or flipping — for SMC bot we expect single entry per cycle
            log.warning("Position already open for %s; ignoring additional entry", order.symbol)

    def _fill_close_via_order(self, order: Order, price: float, ts: int, reason: str) -> None:
        pos = self._positions.get(order.symbol)
        if pos is None:
            order.status = OrderStatus.CANCELED
            return
        notional = price * order.qty
        fee = self._apply_fee(notional)
        order.status = OrderStatus.FILLED
        order.filled_qty = order.qty
        order.avg_fill_price = price
        self._fill_close(order.symbol, price, reason, ts, fee_already=fee)

    def _fill_close(self, symbol: str, price: float, reason: str, ts: int,
                    fee_already: float = 0.0) -> None:
        pos = self._positions.pop(symbol, None)
        if pos is None:
            return
        sign = 1 if pos.side == "long" else -1
        gross = sign * (price - pos.entry_price) * pos.qty
        self._cash += gross
        self._realized_pnl += gross
        # build Trade
        meta = self._open_trade_meta.pop(symbol, {})
        initial_risk = self._initial_risk.pop(symbol, 0.0)
        total_fee = meta.get("fees", 0.0) + fee_already
        net_pnl = gross - total_fee + meta.get("fees", 0.0)  # entry fee already debited from cash
        # Re-shape: gross was added to cash, both fees were already debited at fill time.
        # The "trade pnl" we report is net = gross - entry_fee - exit_fee.
        net_pnl = gross - total_fee
        r_mult = (net_pnl / initial_risk) if initial_risk > 0 else 0.0
        self._trades.append(Trade(
            symbol=symbol,
            side=pos.side,
            entry_ts=meta.get("entry_ts", ts),
            exit_ts=ts,
            entry_price=meta.get("entry_price", pos.entry_price),
            exit_price=price,
            qty=pos.qty,
            pnl=net_pnl,
            fees=total_fee,
            r_multiple=r_mult,
            reason=reason,
        ))

    def _cancel_sibling(self, child: Order) -> None:
        entry_id = self._reverse_bracket.get(child.id)
        if entry_id is None:
            return
        for sib_id in self._brackets.get(entry_id, []):
            if sib_id == child.id:
                continue
            sib = self._orders.get(sib_id)
            if sib and sib.status in (OrderStatus.NEW, OrderStatus.OPEN):
                sib.status = OrderStatus.CANCELED
