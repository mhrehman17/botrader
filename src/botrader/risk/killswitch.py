"""Kill switches: daily-loss and max-drawdown circuit breakers."""
from __future__ import annotations

from datetime import UTC, datetime


class KillSwitch:
    def __init__(self, daily_loss_pct: float, max_drawdown_pct: float):
        self.daily_loss_pct = daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self._day_start_equity: float | None = None
        self._day_key: str | None = None
        self._peak_equity: float = 0.0
        self._tripped: bool = False
        self._reason: str = ""

    @staticmethod
    def _day_key_of(ts_ms: int) -> str:
        return datetime.fromtimestamp(ts_ms / 1000, tz=UTC).strftime("%Y-%m-%d")

    def update(self, ts_ms: int, equity: float) -> tuple[bool, str]:
        """Return (tripped, reason). Once tripped for the day or drawdown, stays so."""
        if self._tripped:
            return True, self._reason

        key = self._day_key_of(ts_ms)
        if self._day_key != key:
            self._day_key = key
            self._day_start_equity = equity

        # Daily loss check
        if self._day_start_equity and self._day_start_equity > 0:
            day_dd = (self._day_start_equity - equity) / self._day_start_equity
            if day_dd >= self.daily_loss_pct:
                self._tripped = True
                self._reason = (
                    f"daily_loss_kill: {day_dd:.2%} >= {self.daily_loss_pct:.2%}"
                )
                return True, self._reason

        # Max drawdown check
        self._peak_equity = max(self._peak_equity, equity)
        if self._peak_equity > 0:
            dd = (self._peak_equity - equity) / self._peak_equity
            if dd >= self.max_drawdown_pct:
                self._tripped = True
                self._reason = (
                    f"max_drawdown_kill: {dd:.2%} >= {self.max_drawdown_pct:.2%}"
                )
                return True, self._reason

        return False, ""

    def reset(self) -> None:
        self._tripped = False
        self._reason = ""
        self._peak_equity = 0.0
        self._day_key = None
        self._day_start_equity = None
