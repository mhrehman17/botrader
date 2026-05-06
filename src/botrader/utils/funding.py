"""Funding-window blackout logic.

Most USDT-margined perpetual futures pay funding every 8 hours at 00:00, 08:00,
and 16:00 UTC. Trading right around the funding flip can be risky for SMC sweeps
because micro-volatility spikes; we expose a helper to skip those windows.
"""
from __future__ import annotations

from datetime import UTC, datetime

_FUNDING_HOURS_UTC = (0, 8, 16)


def in_funding_blackout(ts_ms: int, blackout_minutes: int) -> bool:
    """True if `ts_ms` is within `blackout_minutes` of a funding flip (00/08/16 UTC)."""
    if blackout_minutes <= 0:
        return False
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
    minutes_in_day = dt.hour * 60 + dt.minute
    for h in _FUNDING_HOURS_UTC:
        flip_min = h * 60
        delta = abs(minutes_in_day - flip_min)
        # also wrap around midnight for the 0:00 window
        delta = min(delta, 1440 - delta)
        if delta <= blackout_minutes:
            return True
    return False
