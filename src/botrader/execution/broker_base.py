"""Broker interface — sim, paper, and live brokers conform to this."""
from __future__ import annotations

from typing import Protocol

from ..core.types import Order, Position, Side


class Broker(Protocol):
    def balance(self) -> float: ...
    def equity(self) -> float: ...
    def positions(self) -> list[Position]: ...
    def open_orders(self, symbol: str | None = None) -> list[Order]: ...
    def place_order(self, order: Order) -> Order: ...
    def cancel_order(self, order_id: str) -> None: ...
    def cancel_all(self, symbol: str | None = None) -> None: ...
    def close_position(self, symbol: str) -> None: ...
    def set_leverage(self, symbol: str, leverage: float) -> None: ...

    # Helpful for backtest reporting
    def realized_pnl(self) -> float: ...

    def mark_price(self, symbol: str) -> float | None:
        ...

    def on_bar(self, symbol: str, ts: int, open_: float, high: float, low: float,
               close: float) -> None:
        """Called once per bar so the broker can fill resting orders / update upnl.
        Live brokers may treat this as a no-op."""

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
        """Submit a limit entry plus reduce-only SL and TP. Returns the entry order id."""
