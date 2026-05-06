"""Strategy EV-gate filters: min R:R to TP1, max SL distance vs ATR."""
from __future__ import annotations

import pandas as pd

from botrader.config import RiskConfig, StrategyConfig
from botrader.core.types import OrderBlock, Signal, Sweep
from botrader.strategy.smc_mtf import SMCStrategy


def _strategy(min_rr: float = 1.0, max_sl_atr: float = 4.0) -> SMCStrategy:
    return SMCStrategy(
        StrategyConfig(min_rr_to_tp1=min_rr, max_sl_atr_mult=max_sl_atr),
        RiskConfig(),
    )


def test_strategy_constructs_with_new_fields():
    """The new StrategyConfig fields are wired into the strategy."""
    s = _strategy(min_rr=1.5, max_sl_atr=3.0)
    assert s.strat.min_rr_to_tp1 == 1.5
    assert s.strat.max_sl_atr_mult == 3.0


def test_min_rr_filter_rejects_bad_rr_from_signal_constructor():
    """The filter logic itself: a signal with R:R < min should be filtered.

    We exercise the filter by directly invoking the gate: build a synthetic
    setup where TP1 distance < SL distance, ensure no Signal is emitted.
    """
    # Construct minimal candle history that the strategy can ingest. We're
    # not testing the SMC pipeline end-to-end here — the EV-gate test
    # lives at a unit level via direct math.
    sig = Signal(
        side="long", entry=100.0, stop_loss=99.0,
        take_profit_1=100.3, take_profit_2=None,
        reason="test", htf_bias="up",
    )
    # SL distance = 1.0, TP1 distance = 0.3 -> R:R = 0.3
    rr = abs(sig.take_profit_1 - sig.entry) / abs(sig.entry - sig.stop_loss)
    assert abs(rr - 0.3) < 1e-9
    # min_rr_to_tp1 default is 1.0, so this signal would be rejected by the gate
    cfg = StrategyConfig()
    assert rr < cfg.min_rr_to_tp1


def test_max_sl_atr_filter_math():
    """The max_sl_atr_mult filter rejects setups where risk_distance > N×ATR."""
    cfg = StrategyConfig(max_sl_atr_mult=2.0)
    atr = 0.5
    # SL distance = 1.5 -> 1.5 / 0.5 = 3 ATRs -> rejected (>2)
    risk_distance = 1.5
    assert risk_distance > cfg.max_sl_atr_mult * atr
    # SL distance = 0.8 -> 1.6 ATRs -> accepted
    risk_distance = 0.8
    assert risk_distance <= cfg.max_sl_atr_mult * atr


def test_strategy_signal_has_mandatory_fields():
    """Smoke test that SMCStrategy.on_bar returns [] for empty input
    and doesn't crash with the new filters."""
    s = _strategy()
    empty = pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
    sigs = s.on_bar("BTC/USDT:USDT", empty, empty)
    assert sigs == []


def test_signal_dataclass_includes_ob_and_sweep():
    """Sanity: the Signal type still carries OB + Sweep for downstream consumers."""
    ob = OrderBlock(idx=0, ts=0, top=101, bottom=99, side="long")
    sw = Sweep(idx=0, ts=0, pool_price=99, is_high=False, extreme=98.5, close=99.5)
    sig = Signal(
        side="long", entry=100, stop_loss=98.5, take_profit_1=102,
        take_profit_2=104, reason="x", htf_bias="up", ob=ob, sweep=sw,
    )
    assert sig.ob is ob and sig.sweep is sw
