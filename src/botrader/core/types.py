"""Core domain types for botrader.

These dataclasses are the lingua franca between the SMC detectors, strategy,
risk manager, brokers, and backtest engine. They are intentionally minimal —
no methods that need market context, just data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

SwingKind = Literal["HH", "HL", "LH", "LL"]
StructureEvent = Literal["BOS_UP", "BOS_DOWN", "CHOCH_UP", "CHOCH_DOWN"]
Trend = Literal["up", "down", "none"]
Side = Literal["long", "short"]


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    TAKE_PROFIT_MARKET = "take_profit_market"


class OrderStatus(str, Enum):
    NEW = "new"
    OPEN = "open"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELED = "canceled"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Candle:
    ts: int          # unix ms (open time)
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Swing:
    idx: int
    ts: int
    price: float
    kind: SwingKind  # HH, HL, LH, LL
    is_high: bool


@dataclass
class StructurePoint:
    idx: int
    ts: int
    event: StructureEvent
    price: float
    broken_swing_idx: int


@dataclass
class OrderBlock:
    idx: int                 # bar index of the OB candle
    ts: int
    top: float
    bottom: float
    side: Side               # "long" => bullish OB, "short" => bearish OB
    mitigated: bool = False
    mitigated_idx: int | None = None


@dataclass
class FVG:
    idx: int                 # idx of the third (right) candle
    ts: int
    top: float
    bottom: float
    side: Side               # bullish gap = "long" (price expected up)
    filled: bool = False
    filled_idx: int | None = None


@dataclass
class LiquidityPool:
    is_high: bool
    price: float             # representative pool price
    touches: list[int]       # bar indices that touched
    swept: bool = False
    swept_idx: int | None = None


@dataclass
class Sweep:
    idx: int
    ts: int
    pool_price: float
    is_high: bool            # True = sweep of high pool (bearish sweep)
    extreme: float           # the wick extreme (high if is_high else low)
    close: float


@dataclass
class Signal:
    side: Side
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float | None
    reason: str
    htf_bias: Trend
    ob: OrderBlock | None = None
    sweep: Sweep | None = None
    ts: int = 0


@dataclass
class Order:
    id: str
    symbol: str
    side: Side
    type: OrderType
    qty: float
    price: float | None
    status: OrderStatus = OrderStatus.NEW
    reduce_only: bool = False
    stop_price: float | None = None
    client_id: str | None = None
    filled_qty: float = 0.0
    avg_fill_price: float | None = None


@dataclass
class Position:
    symbol: str
    side: Side
    qty: float                       # signed in math; positive here, side carries direction
    entry_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    leverage: float = 1.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    opened_ts: int = 0


@dataclass
class Trade:
    """A completed round-trip trade (one entry + one or more exits)."""

    symbol: str
    side: Side
    entry_ts: int
    exit_ts: int
    entry_price: float
    exit_price: float
    qty: float
    pnl: float                       # in quote currency, after fees
    fees: float
    r_multiple: float                # pnl / initial_risk
    reason: str = ""


@dataclass
class Equity:
    ts: int
    equity: float
    cash: float
    upnl: float = 0.0


@dataclass
class BacktestResult:
    equity_curve: list[Equity] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
