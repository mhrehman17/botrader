"""Event types for the event-driven engine."""
from __future__ import annotations

from dataclasses import dataclass

from .types import Candle, Order, Signal


@dataclass
class BarEvent:
    symbol: str
    timeframe: str
    candle: Candle


@dataclass
class SignalEvent:
    symbol: str
    signal: Signal


@dataclass
class FillEvent:
    symbol: str
    order: Order
    price: float
    qty: float
    fee: float
    ts: int


@dataclass
class KillEvent:
    reason: str
    ts: int
