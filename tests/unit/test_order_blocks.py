from __future__ import annotations

from botrader.smc.order_blocks import find_order_blocks, ob_entry_price, update_mitigation
from botrader.smc.structure import classify_structure
from tests.conftest import make_df


def test_bullish_ob_is_last_bearish_before_break():
    # establish swing high at idx 4 (high=12)
    # then bearish candle at idx 5, then bullish impulse breaking 12.
    rows = [
        (10, 10, 9, 10, 1),
        (10, 10, 9, 10, 1),
        (10, 10, 9, 10, 1),
        (10, 11, 10, 11, 1),
        (11, 12, 11, 12, 1),  # idx 4: pivot high 12 (uniquely highest)
        (12, 11, 10, 10, 1),  # idx 5: bearish (open 12 close 10)
        (10, 11, 9, 9, 1),    # idx 6: bearish (latest bearish before impulse)
        (9, 14, 9, 13, 1),    # idx 7: impulse close 13 > 12 -> CHOCH_UP
        (13, 14, 12, 13, 1),
        (13, 14, 12, 13, 1),
    ]
    df = make_df(rows)
    state = classify_structure(df, left=2, right=2)
    obs = find_order_blocks(df, state.events)
    assert obs, "expected at least one OB"
    ob = obs[0]
    assert ob.side == "long"
    # OB candle is the last bearish before break (idx 6)
    assert ob.idx == 6
    assert ob.bottom == 9
    assert ob.top == 11

    update_mitigation(obs, df)
    assert not ob.mitigated


def test_ob_entry_price_midpoint():
    from botrader.core.types import OrderBlock
    ob = OrderBlock(idx=0, ts=0, top=110, bottom=100, side="long")
    # depth 0.5 -> midpoint = 105
    assert ob_entry_price(ob, 0.5) == 105
    # depth 0.62 -> 110 - 10*0.62 = 103.8
    assert abs(ob_entry_price(ob, 0.62) - 103.8) < 1e-9
