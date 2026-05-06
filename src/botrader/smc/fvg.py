"""Fair Value Gap (FVG) detection and fill tracking.

3-candle imbalance at bar i (using bars i-2, i-1, i):
  - Bullish FVG if  low[i]  > high[i-2]  -> gap = (high[i-2], low[i])
  - Bearish FVG if  high[i] < low[i-2]   -> gap = (high[i],  low[i-2])

A gap is filled when a later candle's wick covers the gap range.
"""
from __future__ import annotations

import pandas as pd

from ..core.types import FVG


def find_fvgs(df: pd.DataFrame, min_size_bps: float = 0.0) -> list[FVG]:
    if len(df) < 3:
        return []
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    ts = df["ts"].to_numpy()
    n = len(df)
    out: list[FVG] = []
    for i in range(2, n):
        # bullish FVG
        if lows[i] > highs[i - 2]:
            top = float(lows[i])
            bottom = float(highs[i - 2])
            mid = closes[i - 1] or top
            if (top - bottom) / mid * 1e4 >= min_size_bps:
                out.append(FVG(idx=i, ts=int(ts[i]), top=top, bottom=bottom, side="long"))
        # bearish FVG
        elif highs[i] < lows[i - 2]:
            top = float(lows[i - 2])
            bottom = float(highs[i])
            mid = closes[i - 1] or top
            if (top - bottom) / mid * 1e4 >= min_size_bps:
                out.append(FVG(idx=i, ts=int(ts[i]), top=top, bottom=bottom, side="short"))
    return out


def update_fills(fvgs: list[FVG], df: pd.DataFrame) -> None:
    if not fvgs:
        return
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    n = len(df)
    for g in fvgs:
        if g.filled:
            continue
        # An FVG is "filled" the moment price re-enters the imbalance zone.
        # Bullish gap: any later low at or below gap top (i.e., wick into the gap).
        # Bearish gap: any later high at or above gap bottom.
        for i in range(g.idx + 1, n):
            if g.side == "long":
                if lows[i] <= g.top:
                    g.filled = True
                    g.filled_idx = i
                    break
            elif highs[i] >= g.bottom:
                g.filled = True
                g.filled_idx = i
                break
