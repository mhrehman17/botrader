"""SimBroker exit-management tests:

- submit_smc_bracket places entry + SL + TP1(partial) + TP2(remainder).
- TP1 fill triggers a partial close and moves SL to breakeven on the remainder.
- TP2 fill closes the rest.
- modify_stop replaces the active SL.
- MFE tracking and 1R-trailing semantics work (via direct modify_stop calls).
"""
from __future__ import annotations

from botrader.core.types import OrderStatus, OrderType
from botrader.execution.sim_broker import SimBroker


def _bar(broker: SimBroker, sym: str, ts: int, o: float, h: float, l: float, c: float):
    broker.on_bar(sym, ts, o, h, l, c)


def test_smc_bracket_fills_entry_and_activates_children():
    b = SimBroker(initial_cash=10_000, fee_bps=0, slippage_bps=0)
    sym = "BTC/USDT:USDT"
    b.submit_smc_bracket(sym, "long", qty=1.0,
                         entry_price=100.0, stop_loss=99.0,
                         take_profit_1=101.0, take_profit_2=102.0,
                         partial_pct=0.5, client_id="t1")

    # No fill yet (price hasn't reached entry)
    _bar(b, sym, 1, 105, 105, 104, 104)
    assert not b.positions()

    # Entry fills when bar range covers 100
    _bar(b, sym, 2, 100.5, 100.5, 99.5, 100.0)
    pos = b.positions()
    assert len(pos) == 1
    assert pos[0].qty == 1.0
    meta = b.position_meta(sym)
    assert meta is not None
    assert meta["entry_price"] == 100.0
    assert meta["original_sl"] == 99.0
    assert not meta["tp1_filled"]


def test_tp1_fills_partial_and_moves_sl_to_breakeven():
    b = SimBroker(initial_cash=10_000, fee_bps=0, slippage_bps=0)
    sym = "BTC/USDT:USDT"
    b.submit_smc_bracket(sym, "long", qty=1.0,
                         entry_price=100.0, stop_loss=99.0,
                         take_profit_1=101.0, take_profit_2=102.0,
                         partial_pct=0.5, client_id="t2")
    # Fill entry
    _bar(b, sym, 1, 100.0, 100.5, 99.8, 100.2)
    # Hit TP1
    _bar(b, sym, 2, 100.2, 101.5, 100.0, 101.2)
    pos = b.positions()
    assert len(pos) == 1, "partial close: position should still be open"
    assert abs(pos[0].qty - 0.5) < 1e-9
    meta = b.position_meta(sym)
    assert meta["tp1_filled"]
    # SL should now be at breakeven (entry_price)
    assert abs(meta["current_sl"] - 100.0) < 1e-9
    # First trade row recorded with reason take_profit_1
    trades = b.trades()
    assert len(trades) == 1
    assert trades[0].reason == "take_profit_1"
    assert abs(trades[0].qty - 0.5) < 1e-9
    assert trades[0].pnl > 0


def test_tp2_after_tp1_closes_remainder_at_breakeven_or_better():
    b = SimBroker(initial_cash=10_000, fee_bps=0, slippage_bps=0)
    sym = "BTC/USDT:USDT"
    b.submit_smc_bracket(sym, "long", qty=2.0,
                         entry_price=100.0, stop_loss=99.0,
                         take_profit_1=101.0, take_profit_2=102.0,
                         partial_pct=0.5, client_id="t3")
    _bar(b, sym, 1, 100.0, 100.5, 99.8, 100.2)
    _bar(b, sym, 2, 100.2, 101.2, 100.0, 101.0)  # fill TP1, breakeven move
    _bar(b, sym, 3, 101.0, 102.5, 101.0, 102.2)  # fill TP2
    assert not b.positions(), "position should be flat after TP2"
    trades = b.trades()
    assert len(trades) == 2
    assert trades[0].reason == "take_profit_1"
    assert trades[1].reason == "take_profit"  # TP2 is plain take_profit
    # Both trades should be net positive (longs hitting TPs above entry)
    assert all(t.pnl > 0 for t in trades)


def test_breakeven_sl_protects_capital_on_pullback():
    b = SimBroker(initial_cash=10_000, fee_bps=0, slippage_bps=0)
    sym = "BTC/USDT:USDT"
    b.submit_smc_bracket(sym, "long", qty=2.0,
                         entry_price=100.0, stop_loss=99.0,
                         take_profit_1=101.0, take_profit_2=110.0,
                         partial_pct=0.5, client_id="t4")
    _bar(b, sym, 1, 100.0, 100.5, 99.8, 100.2)
    _bar(b, sym, 2, 100.2, 101.5, 100.0, 101.2)  # fill TP1 + breakeven
    # Pullback to 99.5 — should hit breakeven SL at 100.0, NOT the original 99.0
    _bar(b, sym, 3, 101.0, 101.0, 99.5, 99.6)
    assert not b.positions()
    trades = b.trades()
    # TP1 was a winner; second exit at breakeven should be ~0 PnL (near 100.0)
    assert trades[1].reason == "stop_loss"
    assert abs(trades[1].exit_price - 100.0) < 1e-3, f"expected breakeven exit, got {trades[1].exit_price}"


def test_modify_stop_replaces_active_sl():
    b = SimBroker(initial_cash=10_000, fee_bps=0, slippage_bps=0)
    sym = "BTC/USDT:USDT"
    b.submit_smc_bracket(sym, "long", qty=1.0,
                         entry_price=100.0, stop_loss=99.0,
                         take_profit_1=110.0, take_profit_2=None,
                         partial_pct=1.0, client_id="t5")
    _bar(b, sym, 1, 100.0, 100.5, 99.8, 100.2)
    assert b.modify_stop(sym, 99.5) is True
    meta = b.position_meta(sym)
    assert meta["current_sl"] == 99.5
    # Pullback should now stop us out at 99.5, not 99.0
    _bar(b, sym, 2, 100.0, 100.0, 99.4, 99.4)
    assert not b.positions()
    trades = b.trades()
    assert trades[-1].reason == "stop_loss"
    assert abs(trades[-1].exit_price - 99.5) < 1e-3


def test_mfe_tracked_for_long_and_short():
    b = SimBroker(initial_cash=10_000, fee_bps=0, slippage_bps=0)
    # long
    b.submit_smc_bracket("BTC/USDT:USDT", "long", qty=1.0,
                         entry_price=100.0, stop_loss=99.0,
                         take_profit_1=200.0, take_profit_2=None,
                         partial_pct=1.0, client_id="long")
    _bar(b, "BTC/USDT:USDT", 1, 100.0, 100.5, 99.8, 100.2)
    _bar(b, "BTC/USDT:USDT", 2, 100.2, 105.0, 100.0, 104.0)
    _bar(b, "BTC/USDT:USDT", 3, 104.0, 104.5, 102.0, 103.0)
    meta = b.position_meta("BTC/USDT:USDT")
    assert meta["mfe_price"] == 105.0, "MFE = highest high while long"

    # short
    b2 = SimBroker(initial_cash=10_000, fee_bps=0, slippage_bps=0)
    b2.submit_smc_bracket("ETH/USDT:USDT", "short", qty=1.0,
                          entry_price=100.0, stop_loss=101.0,
                          take_profit_1=50.0, take_profit_2=None,
                          partial_pct=1.0, client_id="short")
    _bar(b2, "ETH/USDT:USDT", 1, 100.0, 100.2, 99.5, 99.8)
    _bar(b2, "ETH/USDT:USDT", 2, 99.8, 99.9, 95.0, 96.0)
    meta2 = b2.position_meta("ETH/USDT:USDT")
    assert meta2["mfe_price"] == 95.0, "MFE = lowest low while short"


def test_original_sl_still_triggers_before_tp1():
    """Pre-TP1, the original SL is what protects us."""
    b = SimBroker(initial_cash=10_000, fee_bps=0, slippage_bps=0)
    sym = "BTC/USDT:USDT"
    b.submit_smc_bracket(sym, "long", qty=1.0,
                         entry_price=100.0, stop_loss=99.0,
                         take_profit_1=110.0, take_profit_2=120.0,
                         partial_pct=0.5, client_id="t6")
    _bar(b, sym, 1, 100.0, 100.5, 99.8, 100.2)  # fill entry
    _bar(b, sym, 2, 100.2, 100.3, 98.5, 98.7)   # SL hit at 99.0
    assert not b.positions()
    trades = b.trades()
    assert trades[-1].reason == "stop_loss"
    # SL should fire on the FULL qty (1.0) since TP1 hadn't filled yet
    assert abs(trades[-1].qty - 1.0) < 1e-9
    # All open child orders should be canceled/filled (not lingering)
    for o in b.open_orders(sym):
        assert o.status not in (OrderStatus.OPEN, OrderStatus.NEW)


def test_partial_pct_one_falls_back_to_single_tp():
    """When partial_pct=1.0 (or tp2 is None), there's no TP2; behaves like a single bracket."""
    b = SimBroker(initial_cash=10_000, fee_bps=0, slippage_bps=0)
    sym = "BTC/USDT:USDT"
    b.submit_smc_bracket(sym, "long", qty=1.0,
                         entry_price=100.0, stop_loss=99.0,
                         take_profit_1=101.0, take_profit_2=None,
                         partial_pct=0.5, client_id="t7")
    # only entry, sl, tp1 should exist (no tp2)
    open_orders = b.open_orders(sym)
    types = sorted([o.type for o in open_orders], key=lambda t: t.value)
    assert OrderType.LIMIT in types  # entry
    assert OrderType.STOP_MARKET in types  # SL
    assert OrderType.TAKE_PROFIT_MARKET in types  # TP1 only
    # Exactly one TAKE_PROFIT_MARKET
    tps = [o for o in open_orders if o.type == OrderType.TAKE_PROFIT_MARKET]
    assert len(tps) == 1
    # Full qty on TP1 (since tp2 is None, partial doesn't apply)
    assert abs(tps[0].qty - 1.0) < 1e-9
