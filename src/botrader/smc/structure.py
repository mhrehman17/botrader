"""Market structure: BOS (Break of Structure) and CHoCH (Change of Character).

Algorithm:
- Maintain a `trend` state: 'up' | 'down' | 'none'.
- Track the most recent confirmed swing high (`last_sh`) and swing low (`last_sl`).
- Each new candle (after enough swings exist), test:
    - close > last_sh:
        - if trend == 'up': BOS up (continuation)
        - else: CHoCH up (trend change), trend := 'up'
    - close < last_sl:
        - if trend == 'down': BOS down
        - else: CHoCH down, trend := 'down'
- After a break, the broken swing is "consumed" — we wait for a new swing in
  that direction before re-testing.

This produces a list of StructurePoint events ordered by index, plus a final
trend value that drives the HTF bias used by the strategy.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..core.types import StructurePoint, Swing, Trend
from .swings import detect_swings


@dataclass
class StructureState:
    events: list[StructurePoint]
    trend: Trend
    last_sh: Swing | None
    last_sl: Swing | None


def classify_structure(
    df: pd.DataFrame,
    left: int = 2,
    right: int = 2,
) -> StructureState:
    """Run market structure classification across df. Returns events and final trend."""
    swings = detect_swings(df, left=left, right=right)

    closes = df["close"].to_numpy()
    ts = df["ts"].to_numpy()
    n = len(df)
    if n == 0:
        return StructureState(events=[], trend="none", last_sh=None, last_sl=None)

    # index swings by their *confirmation* index (when the engine learns of them)
    # so we never use future information.
    swings_by_conf: dict[int, list[Swing]] = {}
    for s in swings:
        conf = s.idx + right
        if conf < n:
            swings_by_conf.setdefault(conf, []).append(s)

    events: list[StructurePoint] = []
    trend: Trend = "none"
    last_sh: Swing | None = None
    last_sl: Swing | None = None

    for i in range(n):
        # First, ingest any swings confirmed at this bar
        for s in swings_by_conf.get(i, []):
            if s.is_high:
                last_sh = s
            else:
                last_sl = s

        # Then, test for structural breaks against the swings we already know about
        c = closes[i]
        if last_sh is not None and c > last_sh.price:
            event = "BOS_UP" if trend == "up" else "CHOCH_UP"
            events.append(StructurePoint(
                idx=i, ts=int(ts[i]), event=event, price=float(c),
                broken_swing_idx=last_sh.idx,
            ))
            trend = "up"
            last_sh = None  # consumed; wait for a new swing high
        elif last_sl is not None and c < last_sl.price:
            event = "BOS_DOWN" if trend == "down" else "CHOCH_DOWN"
            events.append(StructurePoint(
                idx=i, ts=int(ts[i]), event=event, price=float(c),
                broken_swing_idx=last_sl.idx,
            ))
            trend = "down"
            last_sl = None

    return StructureState(events=events, trend=trend, last_sh=last_sh, last_sl=last_sl)


def trend_to_bias(trend: Trend) -> Trend:
    """Bias is the trend itself for now — exposed as a hook for future filters."""
    return trend
