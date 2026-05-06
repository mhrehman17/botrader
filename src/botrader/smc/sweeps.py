"""Liquidity sweep detection.

A bearish sweep of a high pool: a candle's wick prints above the pool but the
body closes back below it. Mirror for bullish sweep of a low pool.
"""
from __future__ import annotations

import pandas as pd

from ..core.types import LiquidityPool, Sweep


def detect_sweeps(df: pd.DataFrame, pools: list[LiquidityPool]) -> list[Sweep]:
    if not pools or df.empty:
        return []
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    ts = df["ts"].to_numpy()
    n = len(df)

    sweeps: list[Sweep] = []
    for pool in pools:
        if pool.swept:
            continue
        # only look forward from the latest touch
        start = max(pool.touches) + 1 if pool.touches else 0
        for i in range(start, n):
            if pool.is_high:
                if highs[i] > pool.price and closes[i] < pool.price:
                    sweeps.append(Sweep(
                        idx=i, ts=int(ts[i]),
                        pool_price=pool.price, is_high=True,
                        extreme=float(highs[i]), close=float(closes[i]),
                    ))
                    pool.swept = True
                    pool.swept_idx = i
                    break
            elif lows[i] < pool.price and closes[i] > pool.price:
                sweeps.append(Sweep(
                    idx=i, ts=int(ts[i]),
                    pool_price=pool.price, is_high=False,
                    extreme=float(lows[i]), close=float(closes[i]),
                ))
                pool.swept = True
                pool.swept_idx = i
                break
    sweeps.sort(key=lambda s: s.idx)
    return sweeps
