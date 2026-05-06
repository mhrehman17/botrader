"""Concurrent-position and leverage limits."""
from __future__ import annotations

from ..core.types import Position


class LimitChecker:
    def __init__(self, max_concurrent_positions: int, max_leverage: float):
        self.max_concurrent_positions = max_concurrent_positions
        self.max_leverage = max_leverage

    def can_open(self, open_positions: list[Position]) -> bool:
        return len(open_positions) < self.max_concurrent_positions

    def leverage_ok(self, total_notional: float, equity: float) -> bool:
        if equity <= 0:
            return False
        return (total_notional / equity) <= self.max_leverage
