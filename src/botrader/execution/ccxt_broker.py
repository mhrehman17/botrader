"""ccxt-backed broker for live and testnet futures trading.

This adapter targets USDT-margined linear perpetuals with reduce-only stop-loss
and take-profit (bracket-style). Behavior may differ slightly per exchange;
test against the testnet first.
"""
from __future__ import annotations

import logging
import uuid
from typing import Literal

from ..config import ExchangeConfig
from ..core.types import Order, OrderStatus, OrderType, Position, Side

log = logging.getLogger(__name__)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class CcxtBroker:
    def __init__(self, exchange_cfg: ExchangeConfig, mode: Literal["testnet", "mainnet"]):
        import ccxt  # noqa: PLC0415

        klass = getattr(ccxt, exchange_cfg.id, None)
        if klass is None:
            raise ValueError(f"Unknown exchange id: {exchange_cfg.id}")
        ex_kwargs = {
            "apiKey": exchange_cfg.api_key,
            "secret": exchange_cfg.api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "swap", **(exchange_cfg.options or {})},
        }
        self._ex = klass(ex_kwargs)
        use_sandbox = mode == "testnet" or exchange_cfg.testnet
        if use_sandbox and hasattr(self._ex, "set_sandbox_mode"):
            self._ex.set_sandbox_mode(True)
        self._ex.load_markets()
        self._mode = mode
        self._mark_cache: dict[str, float] = {}

    # -- read paths --------------------------------------------------------
    def balance(self) -> float:
        bal = self._ex.fetch_balance()
        # for USDT linear, free + used USDT
        usdt = bal.get("USDT") or bal.get("total", {}).get("USDT", 0)
        if isinstance(usdt, dict):
            return float(usdt.get("total", 0))
        return float(usdt or 0)

    def equity(self) -> float:
        # most ccxt exchanges expose total wallet equity in fetch_balance['info']
        bal = self._ex.fetch_balance()
        info = bal.get("info") or {}
        # Binance USDT-M: totalWalletBalance + totalUnrealizedProfit
        try:
            wallet = float(info.get("totalWalletBalance", 0))
            upnl = float(info.get("totalUnrealizedProfit", 0))
            return wallet + upnl
        except Exception:
            return self.balance()

    def positions(self) -> list[Position]:
        try:
            raws = self._ex.fetch_positions()
        except Exception as e:  # noqa: BLE001
            log.warning("fetch_positions failed: %s", e)
            return []
        out: list[Position] = []
        for r in raws:
            qty = float(r.get("contracts") or r.get("contractSize") or 0)
            if qty == 0:
                continue
            side: Side = "long" if (r.get("side") or "").lower() == "long" else "short"
            out.append(Position(
                symbol=r.get("symbol") or "",
                side=side,
                qty=abs(qty),
                entry_price=float(r.get("entryPrice") or 0),
                unrealized_pnl=float(r.get("unrealizedPnl") or 0),
                leverage=float(r.get("leverage") or 1),
            ))
        return out

    def open_orders(self, symbol: str | None = None) -> list[Order]:
        try:
            raws = self._ex.fetch_open_orders(symbol) if symbol else self._ex.fetch_open_orders()
        except Exception as e:  # noqa: BLE001
            log.warning("fetch_open_orders failed: %s", e)
            return []
        out = []
        for r in raws:
            out.append(Order(
                id=str(r.get("id")),
                symbol=r.get("symbol") or "",
                side="long" if r.get("side") == "buy" else "short",
                type=OrderType(r.get("type") or "limit"),
                qty=float(r.get("amount") or 0),
                price=float(r["price"]) if r.get("price") else None,
                status=OrderStatus.OPEN,
                client_id=r.get("clientOrderId"),
            ))
        return out

    def realized_pnl(self) -> float:
        return 0.0  # not tracked locally; rely on exchange ledger

    def mark_price(self, symbol: str) -> float | None:
        return self._mark_cache.get(symbol)

    # -- write paths -------------------------------------------------------
    def place_order(self, order: Order) -> Order:
        side = "buy" if order.side == "long" else "sell"
        params: dict = {}
        if order.reduce_only:
            params["reduceOnly"] = True
        if order.client_id:
            params["clientOrderId"] = order.client_id
        sym, qty = order.symbol, order.qty
        if order.type == OrderType.STOP_MARKET and order.stop_price is not None:
            params["stopPrice"] = order.stop_price
            r = self._ex.create_order(sym, "STOP_MARKET", side, qty, None, params)
        elif order.type == OrderType.TAKE_PROFIT_MARKET and order.stop_price is not None:
            params["stopPrice"] = order.stop_price
            r = self._ex.create_order(sym, "TAKE_PROFIT_MARKET", side, qty, None, params)
        elif order.type == OrderType.LIMIT:
            r = self._ex.create_order(sym, "LIMIT", side, qty, order.price, params)
        else:
            r = self._ex.create_order(order.symbol, "MARKET", side, order.qty, None, params)
        order.id = str(r.get("id"))
        order.status = OrderStatus.OPEN
        return order

    def cancel_order(self, order_id: str) -> None:
        try:
            self._ex.cancel_order(order_id)
        except Exception as e:  # noqa: BLE001
            log.warning("cancel_order(%s) failed: %s", order_id, e)

    def cancel_all(self, symbol: str | None = None) -> None:
        try:
            if symbol:
                self._ex.cancel_all_orders(symbol)
            else:
                # cancel per symbol since not all exchanges support global
                for o in self.open_orders():
                    self._ex.cancel_order(o.id, o.symbol)
        except Exception as e:  # noqa: BLE001
            log.warning("cancel_all failed: %s", e)

    def close_position(self, symbol: str) -> None:
        for p in self.positions():
            if p.symbol != symbol:
                continue
            opp_side = "sell" if p.side == "long" else "buy"
            try:
                self._ex.create_order(symbol, "MARKET", opp_side, p.qty, None, {"reduceOnly": True})
            except Exception as e:  # noqa: BLE001
                log.warning("close_position failed: %s", e)

    def set_leverage(self, symbol: str, leverage: float) -> None:
        try:
            self._ex.set_leverage(int(leverage), symbol)
        except Exception as e:  # noqa: BLE001
            log.warning("set_leverage failed: %s", e)

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
        client_id = client_id or _new_id()
        entry = Order(id="", symbol=symbol, side=side, type=OrderType.LIMIT,
                      qty=qty, price=entry_price, client_id=client_id)
        self.place_order(entry)
        sl = Order(id="", symbol=symbol,
                   side="short" if side == "long" else "long",
                   type=OrderType.STOP_MARKET, qty=qty, price=None,
                   stop_price=stop_loss, reduce_only=True,
                   client_id=f"sl-{client_id}")
        self.place_order(sl)
        tp = Order(id="", symbol=symbol,
                   side="short" if side == "long" else "long",
                   type=OrderType.TAKE_PROFIT_MARKET, qty=qty, price=None,
                   stop_price=take_profit, reduce_only=True,
                   client_id=f"tp-{client_id}")
        self.place_order(tp)
        return entry.id

    def on_bar(
        self, symbol: str, ts: int,
        open_: float, high: float, low: float, close: float,
    ) -> None:
        self._mark_cache[symbol] = close
