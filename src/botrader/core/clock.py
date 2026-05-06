"""Clock abstraction so the same code path runs in backtest (sim time) and live (wall time)."""
from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    def now_ms(self) -> int: ...


class RealClock:
    def now_ms(self) -> int:
        return int(time.time() * 1000)


class SimClock:
    def __init__(self, start_ms: int = 0):
        self._now = start_ms

    def now_ms(self) -> int:
        return self._now

    def set(self, ts_ms: int) -> None:
        self._now = ts_ms

    def advance(self, ms: int) -> None:
        self._now += ms
