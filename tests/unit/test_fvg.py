from __future__ import annotations

from botrader.smc.fvg import find_fvgs, update_fills
from tests.conftest import make_df


def test_bullish_fvg_detected_and_filled():
    # candle 0: high 100. candle 1: high 110, low 105 (impulse). candle 2: low 106.
    # bullish FVG = (high[0]=100, low[2]=106)
    rows = [
        (95, 100, 95, 99, 1),
        (99, 110, 105, 109, 1),
        (109, 112, 106, 111, 1),
        (111, 113, 110, 112, 1),
        (112, 113, 102, 103, 1),  # low 102 enters gap (<=106) -> fill
    ]
    df = make_df(rows)
    fvgs = find_fvgs(df)
    assert len(fvgs) == 1
    g = fvgs[0]
    assert g.side == "long"
    assert g.bottom == 100
    assert g.top == 106
    update_fills(fvgs, df)
    assert g.filled
    assert g.filled_idx == 4


def test_bearish_fvg_detected():
    rows = [
        (110, 112, 105, 106, 1),  # low 105
        (106, 108, 101, 102, 1),  # impulse down
        (102, 100, 98, 99, 1),    # high 100 < low[0]=105 -> bearish FVG
    ]
    df = make_df(rows)
    fvgs = find_fvgs(df)
    assert len(fvgs) == 1
    g = fvgs[0]
    assert g.side == "short"
    assert g.bottom == 100
    assert g.top == 105
