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
        # SMC-bracket metadata: tracks entry/SL/TP1/TP2 ids, partial state, MFE, original SL.
        self._smc_meta: dict[str, dict] = {}

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

    def submit_smc_bracket(
        self,
        symbol: str,
        side: Side,
        qty: float,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: float | None,
        partial_pct: float = 0.5,
        client_id: str | None = None,
    ) -> str:
        """Place entry + SL + TP1 (partial) + TP2 (remainder).

        On TP1 fill the broker auto-cancels the original SL and replaces it with
        a breakeven-level SL on the remaining qty. If `take_profit_2` is None
        or partial_pct >= 1, behaves like a regular single-TP bracket.
        """
        partial_pct = max(0.0, min(1.0, partial_pct))
        qty1 = qty * partial_pct if take_profit_2 is not None else qty
        qty2 = qty - qty1

        entry = Order(
            id=_new_id(), symbol=symbol, side=side, type=OrderType.LIMIT,
            qty=qty, price=entry_price, client_id=client_id,
        )
        self.place_order(entry)

        opp: Side = "short" if side == "long" else "long"
        sl = Order(
            id=_new_id(), symbol=symbol, side=opp,
            type=OrderType.STOP_MARKET, qty=qty, price=None, stop_price=stop_loss,
            reduce_only=True, client_id=f"sl-{client_id}" if client_id else None,
        )
        self.place_order(sl)
        sl.status = OrderStatus.NEW

        children = [sl.id]
        tp1 = None
        tp2 = None
        if qty1 > 0:
            tp1 = Order(
                id=_new_id(), symbol=symbol, side=opp,
                type=OrderType.TAKE_PROFIT_MARKET, qty=qty1, price=take_profit_1,
                stop_price=take_profit_1, reduce_only=True,
                client_id=f"tp1-{client_id}" if client_id else None,
            )
            self.place_order(tp1)
            tp1.status = OrderStatus.NEW
            children.append(tp1.id)
        if qty2 > 0 and take_profit_2 is not None:
            tp2 = Order(
                id=_new_id(), symbol=symbol, side=opp,
                type=OrderType.TAKE_PROFIT_MARKET, qty=qty2, price=take_profit_2,
                stop_price=take_profit_2, reduce_only=True,
                client_id=f"tp2-{client_id}" if client_id else None,
            )
            self.place_order(tp2)
            tp2.status = OrderStatus.NEW
            children.append(tp2.id)

        self._brackets[entry.id] = children
        for cid in children:
            self._reverse_bracket[cid] = entry.id

        self._initial_risk[symbol] = abs(entry_price - stop_loss) * qty
        self._smc_meta[symbol] = {
            "entry_id": entry.id,
            "sl_id": sl.id,
            "tp1_id": tp1.id if tp1 else None,
            "tp2_id": tp2.id if tp2 else None,
            "entry_price": entry_price,
            "original_sl": stop_loss,
            "side": side,
            "tp1_filled": False,
            "mfe_price": entry_price,
        }
        return entry.id

    def modify_stop(self, symbol: str, new_stop: float) -> bool:
        """Cancel the current SL and place a new STOP_MARKET at `new_stop` for the
        open position's remaining qty. Returns True if modified."""
        meta = self._smc_meta.get(symbol)
        pos = self._positions.get(symbol)
        if meta is None or pos is None:
            return False
        old_sl_id = meta.get("sl_id")
        if old_sl_id is None:
            return False
        old = self._orders.get(old_sl_id)
        if old is None or old.status not in (OrderStatus.OPEN, OrderStatus.NEW):
            return False
        old.status = OrderStatus.CANCELED
        opp: Side = "short" if pos.side == "long" else "long"
        new_sl = Order(
            id=_new_id(), symbol=symbol, side=opp,
            type=OrderType.STOP_MARKET, qty=pos.qty, price=None, stop_price=new_stop,
            reduce_only=True,
            client_id=(old.client_id + "-mod") if old.client_id else None,
        )
        self.place_order(new_sl)  # opens immediately
        meta["sl_id"] = new_sl.id
        # link to bracket so cancel-all-on-fill still works
        entry_id = self._reverse_bracket.get(old_sl_id)
        if entry_id:
            self._reverse_bracket[new_sl.id] = entry_id
            children = self._brackets.get(entry_id, [])
            if old_sl_id in children:
                children[children.index(old_sl_id)] = new_sl.id
        return True

    def position_meta(self, symbol: str) -> dict | None:
        """Return SMC-bracket metadata for an open position (entry_price, original_sl,
        current_sl_price, mfe_price, side, tp1_filled). None if no position."""
        meta = self._smc_meta.get(symbol)
        pos = self._positions.get(symbol)
        if meta is None or pos is None:
            return None
        sl = self._orders.get(meta.get("sl_id"))
        return {
            "entry_price": meta["entry_price"],
            "original_sl": meta["original_sl"],
            "current_sl": sl.stop_price if sl else None,
            "mfe_price": meta["mfe_price"],
            "side": meta["side"],
            "tp1_filled": meta["tp1_filled"],
        }

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

        # Track MFE for trailing logic (engine reads via position_meta)
        meta = self._smc_meta.get(symbol)
        if meta is not None and symbol in self._positions:
            if meta["side"] == "long":
                meta["mfe_price"] = max(meta["mfe_price"], high)
            else:
                meta["mfe_price"] = min(meta["mfe_price"], low)

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
                    is_tp1 = bool(meta) and o.id == meta.get("tp1_id")
                    reason = "take_profit_1" if is_tp1 else "take_profit"
                    self._fill_close_via_order(o, fill_px, ts, reason=reason)
                    if is_tp1:
                        # Move SL to breakeven on the remaining qty (don't cancel siblings).
                        meta["tp1_filled"] = True
                        self._move_sl_to_breakeven(symbol)
                    else:
                        self._cancel_sibling(o)

    def _move_sl_to_breakeven(self, symbol: str) -> None:
        meta = self._smc_meta.get(symbol)
        pos = self._positions.get(symbol)
        if meta is None or pos is None:
            return
        # The original SL was placed for full qty; with a partial close it may now
        # over-size the position. We replace it with a fresh SL at entry_price for
        # the remaining qty.
        self.modify_stop(symbol, meta["entry_price"])

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
        # Clamp closing qty to current position (partial fills welcome).
        close_qty = min(order.qty, pos.qty)
        notional = price * close_qty
        fee = self._apply_fee(notional)
        order.status = OrderStatus.FILLED
        order.filled_qty = close_qty
        order.avg_fill_price = price
        self._fill_close(order.symbol, price, reason, ts, close_qty=close_qty, fee_already=fee)

    def _fill_close(
        self,
        symbol: str,
        price: float,
        reason: str,
        ts: int,
        close_qty: float | None = None,
        fee_already: float = 0.0,
    ) -> None:
        pos = self._positions.get(symbol)
        if pos is None:
            return
        qty_to_close = pos.qty if close_qty is None else min(close_qty, pos.qty)
        if qty_to_close <= 0:
            return

        sign = 1 if pos.side == "long" else -1
        gross = sign * (price - pos.entry_price) * qty_to_close
        self._cash += gross
        self._realized_pnl += gross

        meta = self._open_trade_meta.get(symbol, {})
        initial_risk_total = self._initial_risk.get(symbol, 0.0)
        # Pro-rate the initial-risk and entry-fee allocation to this slice.
        share = qty_to_close / pos.qty if pos.qty > 0 else 1.0
        entry_fee_alloc = meta.get("fees", 0.0) * share
        initial_risk_alloc = initial_risk_total * share
        total_fee = entry_fee_alloc + fee_already
        net_pnl = gross - total_fee
        r_mult = (net_pnl / initial_risk_alloc) if initial_risk_alloc > 0 else 0.0
        self._trades.append(Trade(
            symbol=symbol,
            side=pos.side,
            entry_ts=meta.get("entry_ts", ts),
            exit_ts=ts,
            entry_price=meta.get("entry_price", pos.entry_price),
            exit_price=price,
            qty=qty_to_close,
            pnl=net_pnl,
            fees=total_fee,
            r_multiple=r_mult,
            reason=reason,
        ))

        remaining = pos.qty - qty_to_close
        if remaining <= 0:
            self._positions.pop(symbol, None)
            self._open_trade_meta.pop(symbol, None)
            self._initial_risk.pop(symbol, None)
            self._smc_meta.pop(symbol, None)
        else:
            pos.qty = remaining
            # remaining entry-fee + remaining initial-risk stay attached to the position
            if "fees" in meta:
                meta["fees"] -= entry_fee_alloc
            self._initial_risk[symbol] = initial_risk_total - initial_risk_alloc

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
