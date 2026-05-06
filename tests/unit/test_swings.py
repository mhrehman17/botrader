from __future__ import annotations

from botrader.smc.swings import detect_swings
from tests.conftest import make_df


def test_swing_high_detected_in_synthetic_series():
    # a clear swing high at index 4 (price 13)
    rows = [
        (10, 10, 9, 10, 1),
        (10, 11, 10, 11, 1),
        (11, 11, 10, 10, 1),
        (10, 12, 10, 11, 1),
        (11, 13, 11, 12, 1),  # idx 4: swing high candidate (peak)
        (12, 12, 10, 11, 1),
        (11, 11, 9, 10, 1),
        (10, 10, 8, 9, 1),
        (9,  9,  7, 8, 1),
    ]
    df = make_df(rows)
    swings = detect_swings(df, left=2, right=2)
    assert any(s.is_high and s.idx == 4 and s.price == 13 for s in swings)


def test_swing_low_then_higher_low_labeling():
    # two swing lows: first at 5, second at 6 -> second is HL
    rows = [
        (10, 10, 9,  10, 1),
        (10, 10, 8,  9,  1),
        (9,  9,  7,  8,  1),
        (8,  8,  5,  7,  1),  # idx 3: low pivot (5)
        (7,  9,  7,  8,  1),
        (8,  10, 8,  9,  1),
        (9,  10, 9,  10, 1),
        (10, 10, 8,  9,  1),
        (9,  9,  6,  8,  1),  # idx 8: low pivot (6) -> HL
        (8,  9,  8,  9,  1),
        (9,  10, 9,  10, 1),
        (10, 11, 10, 11, 1),
    ]
    df = make_df(rows)
    swings = detect_swings(df, left=2, right=2)
    lows = [s for s in swings if not s.is_high]
    assert len(lows) >= 2
    assert lows[0].kind == "HL"  # first low has no prior, defaulted to HL
    assert lows[1].kind == "HL"  # 6 > 5
