from __future__ import annotations

from botrader.smc.structure import classify_structure
from tests.conftest import make_df


def test_bos_up_then_choch_down():
    # build a sequence: rising swings -> close breaks high (BOS_UP),
    # then a swing low forms, and a later close breaks below it (CHOCH_DOWN).
    rows = [
        # establish a swing low around idx 3 (low=8)
        (10, 11, 9, 10, 1),
        (10, 11, 9, 10, 1),
        (10, 10, 9, 9, 1),
        (9, 9, 8, 8, 1),       # idx 3: pivot low (8)
        (8, 9, 8, 9, 1),
        (9, 11, 9, 10, 1),
        # establish a swing high around idx 7 (high=13)
        (10, 12, 10, 11, 1),
        (11, 13, 11, 12, 1),   # idx 7: pivot high (13)
        (12, 12, 11, 11, 1),
        (11, 12, 10, 11, 1),
        # now break above 13 -> BOS_UP (since trend is 'none', it's CHOCH_UP per classifier semantics)
        (11, 14, 11, 14, 1),   # idx 10: close 14 > 13
        # establish a new pivot high around idx 13 (15)
        (14, 14, 13, 13, 1),
        (13, 14, 12, 13, 1),
        (13, 15, 13, 14, 1),   # idx 13: pivot high (15)
        (14, 14, 13, 13, 1),
        (13, 13, 11, 12, 1),
        # establish a new pivot low around idx 17 (10)
        (12, 12, 11, 11, 1),
        (11, 11, 10, 10, 1),   # idx 17: pivot low (10)
        (10, 11, 10, 11, 1),
        (11, 12, 10, 11, 1),
        # close below 10 -> after up-trend -> CHOCH_DOWN
        (11, 11, 8, 9, 1),     # idx 21
    ]
    df = make_df(rows)
    state = classify_structure(df, left=2, right=2)
    events = [e.event for e in state.events]
    assert "CHOCH_UP" in events  # first break creates CHoCH (trend was none)
    assert "CHOCH_DOWN" in events  # later break against up-trend
    # final trend should be 'down' since CHoCH-down was last
    assert state.trend == "down"


def test_no_lookahead_with_unconfirmed_swings():
    # if we feed too few bars, no events should fire
    rows = [(10, 11, 9, 10, 1)] * 3
    df = make_df(rows)
    state = classify_structure(df, left=2, right=2)
    assert state.events == []
    assert state.trend == "none"
