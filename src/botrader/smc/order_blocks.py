"""Order Block (OB) detection and mitigation tracking.

A bullish OB is the last bearish (down-close) candle before an impulsive move
that breaks structure to the upside. A bearish OB is the mirror.

Mitigation: an OB is considered "mitigated" once a later candle closes back
through its body. While unmitigated, the zone is considered actionable for
re-entry.
"""
from __future__ import annotations

import pandas as pd

from ..core.types import OrderBlock, StructurePoint


def find_order_blocks(
    df: pd.DataFrame,
    structure_events: list[StructurePoint],
    max_lookback: int = 20,
) -> list[OrderBlock]:
    """For each BOS/CHoCH up event, find the bullish OB; mirror for down events."""
    if not structure_events:
        return []

    opens = df["open"].to_numpy()
    closes = df["close"].to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    ts = df["ts"].to_numpy()

    obs: list[OrderBlock] = []
    for ev in structure_events:
        k = ev.idx
        is_up = ev.event in ("BOS_UP", "CHOCH_UP")
        # scan backwards for the first candle of the opposite color
        lo = max(0, k - max_lookback)
        ob_idx: int | None = None
        for j in range(k - 1, lo - 1, -1):
            bearish = closes[j] < opens[j]
            bullish = closes[j] > opens[j]
            if is_up and bearish:
                ob_idx = j
                break
            if not is_up and bullish:
                ob_idx = j
                break
        if ob_idx is None:
            continue
        obs.append(OrderBlock(
            idx=ob_idx,
            ts=int(ts[ob_idx]),
            top=float(highs[ob_idx]),
            bottom=float(lows[ob_idx]),
            side="long" if is_up else "short",
        ))
    return obs


def update_mitigation(obs: list[OrderBlock], df: pd.DataFrame) -> None:
    """Mark OBs mitigated when a later candle closes through them."""
    closes = df["close"].to_numpy()
    n = len(df)
    for ob in obs:
        if ob.mitigated:
            continue
        for i in range(ob.idx + 1, n):
            c = float(closes[i])
            if ob.side == "long" and c < ob.bottom:
                ob.mitigated = True
                ob.mitigated_idx = i
                break
            if ob.side == "short" and c > ob.top:
                ob.mitigated = True
                ob.mitigated_idx = i
                break


def ob_entry_price(ob: OrderBlock, ote_depth: float = 0.5) -> float:
    """Compute the limit-order entry price within an OB.

    ote_depth = 0.5 -> midpoint
    ote_depth = 0.62 -> 62% retracement (closer to OB extreme for longs)
    """
    if ob.side == "long":
        # for longs, deeper = closer to bottom
        return ob.top - (ob.top - ob.bottom) * ote_depth
    return ob.bottom + (ob.top - ob.bottom) * ote_depth
