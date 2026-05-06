from __future__ import annotations

from botrader.core.types import LiquidityPool
from botrader.smc.sweeps import detect_sweeps
from tests.conftest import make_df


def test_bearish_sweep_of_high_pool():
    rows = [
        (100, 100, 99, 99.5, 1),
        (99.5, 100, 99, 99.8, 1),
        (99.8, 101.5, 99.5, 99.7, 1),  # idx 2: wick to 101.5 above 100, close 99.7 below
    ]
    df = make_df(rows)
    pool = LiquidityPool(is_high=True, price=100.0, touches=[0])
    sweeps = detect_sweeps(df, [pool])
    assert len(sweeps) == 1
    s = sweeps[0]
    assert s.is_high
    assert s.idx == 2
    assert s.extreme == 101.5
    assert pool.swept


def test_bullish_sweep_of_low_pool():
    rows = [
        (50, 51, 49.5, 50.5, 1),
        (50.5, 51, 49.7, 50.2, 1),
        (50.2, 50.5, 48.5, 49.8, 1),  # wick to 48.5, close 49.8 > 49 -> bullish sweep
    ]
    df = make_df(rows)
    pool = LiquidityPool(is_high=False, price=49.0, touches=[0])
    sweeps = detect_sweeps(df, [pool])
    assert len(sweeps) == 1
    assert not sweeps[0].is_high
