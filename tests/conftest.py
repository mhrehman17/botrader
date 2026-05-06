"""Shared test helpers."""
from __future__ import annotations

import pandas as pd


def make_df(rows: list[tuple[float, float, float, float, float]], start_ts: int = 1_700_000_000_000,
            step_ms: int = 60_000) -> pd.DataFrame:
    """Build an OHLCV DataFrame from a list of (open, high, low, close, volume) tuples."""
    data = []
    ts = start_ts
    for o, h, l, c, v in rows:
        data.append((ts, o, h, l, c, v))
        ts += step_ms
    return pd.DataFrame(data, columns=["ts", "open", "high", "low", "close", "volume"])
