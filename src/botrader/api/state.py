"""Process-wide bot state. Single source of truth for the API to read from."""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd

from ..core.types import Equity, Position, Trade

Mode = Literal["paper", "testnet", "mainnet"]


@dataclass
class ScanRow:
    symbol: str
    bias: str                       # "up" | "down" | "none"
    state: str                      # "idle" | "waiting_sweep" | "waiting_choch" | "armed"
    target_price: float | None
    last_close: float
    ts: int


@dataclass
class BotState:
    mode: Mode | None = None
    running: bool = False
    started_at: int = 0
    stop_reason: str = ""
    equity_curve: deque = field(default_factory=lambda: deque(maxlen=2000))
    positions: list[Position] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    scan: dict[str, ScanRow] = field(default_factory=dict)
    candles: dict[tuple[str, str], pd.DataFrame] = field(default_factory=dict)
    killswitch: dict[str, Any] = field(default_factory=lambda: {
        "tripped": False, "reason": "", "peak_equity": 0.0, "day_start_equity": 0.0,
    })

    _lock: threading.RLock = field(default_factory=threading.RLock)

    # ---- mutators (broker/runtime side) ----
    def set_mode(self, mode: Mode | None) -> None:
        with self._lock:
            self.mode = mode

    def set_running(self, running: bool, reason: str = "") -> None:
        with self._lock:
            self.running = running
            if not running:
                self.stop_reason = reason

    def push_equity(self, eq: Equity) -> None:
        with self._lock:
            self.equity_curve.append(eq)

    def set_positions(self, positions: list[Position]) -> None:
        with self._lock:
            self.positions = list(positions)

    def push_trade(self, t: Trade) -> None:
        with self._lock:
            self.trades.append(t)

    def set_scan(self, rows: dict[str, ScanRow]) -> None:
        with self._lock:
            self.scan = dict(rows)

    def set_candles(self, symbol: str, tf: str, df: pd.DataFrame) -> None:
        with self._lock:
            self.candles[(symbol, tf)] = df.copy()

    def set_killswitch(self, **kw: Any) -> None:
        with self._lock:
            self.killswitch.update(kw)

    # ---- snapshots (API side) ----
    def snapshot_equity(self) -> list[Equity]:
        with self._lock:
            return list(self.equity_curve)

    def snapshot_positions(self) -> list[Position]:
        with self._lock:
            return list(self.positions)

    def snapshot_trades(self, limit: int = 50) -> list[Trade]:
        with self._lock:
            if limit <= 0:
                return list(self.trades)
            return list(self.trades[-limit:])[::-1]  # newest first

    def snapshot_scan(self) -> list[ScanRow]:
        with self._lock:
            return list(self.scan.values())

    def snapshot_candles(self, symbol: str, tf: str) -> pd.DataFrame | None:
        with self._lock:
            return self.candles.get((symbol, tf))


_STATE: BotState | None = None
_STATE_LOCK = threading.Lock()


def get_state() -> BotState:
    global _STATE
    with _STATE_LOCK:
        if _STATE is None:
            _STATE = BotState()
        return _STATE


def reset_state() -> None:
    """Test helper."""
    global _STATE
    with _STATE_LOCK:
        _STATE = BotState()
