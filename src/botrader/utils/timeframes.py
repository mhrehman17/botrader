"""Timeframe parsing helpers."""
from __future__ import annotations

_UNIT_MS = {
    "s": 1_000,
    "m": 60_000,
    "h": 3_600_000,
    "d": 86_400_000,
    "w": 604_800_000,
}


def tf_to_ms(tf: str) -> int:
    """Convert a ccxt-style timeframe ('5m', '1h', '1d') to milliseconds."""
    if not tf or len(tf) < 2:
        raise ValueError(f"Invalid timeframe: {tf!r}")
    unit = tf[-1].lower()
    if unit not in _UNIT_MS:
        raise ValueError(f"Unknown timeframe unit in {tf!r}")
    try:
        n = int(tf[:-1])
    except ValueError as e:
        raise ValueError(f"Invalid timeframe number in {tf!r}") from e
    return n * _UNIT_MS[unit]


def floor_to_tf(ts_ms: int, tf: str) -> int:
    step = tf_to_ms(tf)
    return (ts_ms // step) * step
