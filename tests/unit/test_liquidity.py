from __future__ import annotations

from botrader.core.types import Swing
from botrader.smc.liquidity import find_liquidity_pools


def test_equal_highs_pool():
    swings = [
        Swing(idx=10, ts=0, price=100.00, kind="HH", is_high=True),
        Swing(idx=20, ts=0, price=100.04, kind="LH", is_high=True),  # within 5 bps of 100.00
        Swing(idx=30, ts=0, price=110.00, kind="HH", is_high=True),
    ]
    pools = find_liquidity_pools(swings, tolerance_bps=5, min_touches=2)
    assert len(pools) == 1
    p = pools[0]
    assert p.is_high is True
    assert abs(p.price - 100.02) < 0.001
    assert sorted(p.touches) == [10, 20]


def test_equal_lows_pool():
    swings = [
        Swing(idx=5, ts=0, price=50.00, kind="LL", is_high=False),
        Swing(idx=15, ts=0, price=50.02, kind="HL", is_high=False),
    ]
    pools = find_liquidity_pools(swings, tolerance_bps=5, min_touches=2)
    assert len(pools) == 1
    assert pools[0].is_high is False
