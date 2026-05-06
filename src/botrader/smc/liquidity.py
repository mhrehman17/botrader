"""Liquidity pool detection — equal highs / equal lows.

We cluster confirmed swing highs (or lows) where pairwise price distance is
within `tolerance_bps`. A pool needs at least `min_touches` constituents.
"""
from __future__ import annotations

from ..core.types import LiquidityPool, Swing


def _cluster_prices(
    swings: list[Swing], tolerance_bps: float, min_touches: int,
) -> list[LiquidityPool]:
    if not swings:
        return []
    is_high = swings[0].is_high
    # sort by price
    items = sorted(swings, key=lambda s: s.price)
    pools: list[LiquidityPool] = []
    i = 0
    n = len(items)
    while i < n:
        cluster = [items[i]]
        j = i + 1
        while j < n:
            base = cluster[0].price
            if abs(items[j].price - base) / base * 1e4 <= tolerance_bps:
                cluster.append(items[j])
                j += 1
            else:
                break
        if len(cluster) >= min_touches:
            avg_price = sum(s.price for s in cluster) / len(cluster)
            pools.append(LiquidityPool(
                is_high=is_high,
                price=avg_price,
                touches=[s.idx for s in cluster],
            ))
        i = j
    return pools


def find_liquidity_pools(
    swings: list[Swing],
    tolerance_bps: float = 5.0,
    min_touches: int = 2,
) -> list[LiquidityPool]:
    """Return pools of equal highs and equal lows."""
    highs = [s for s in swings if s.is_high]
    lows = [s for s in swings if not s.is_high]
    return (
        _cluster_prices(highs, tolerance_bps, min_touches)
        + _cluster_prices(lows, tolerance_bps, min_touches)
    )
