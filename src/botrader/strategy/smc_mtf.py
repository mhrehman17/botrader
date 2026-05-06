"""Multi-timeframe SMC strategy.

Pipeline (run on every closed LTF bar):

  1. Compute HTF structure -> bias (up/down/none).
  2. Compute HTF liquidity pools -> target = nearest opposing untapped pool.
  3. Compute LTF structure, OBs, FVGs, liquidity, sweeps.
  4. State-machine per symbol:
       a. Need HTF bias != none AND htf target exists.
       b. Wait for an LTF sweep aligned with HTF bias
          (longs sweep an LTF low pool; shorts sweep an LTF high pool).
       c. Wait for an LTF CHoCH in the HTF direction after the sweep.
       d. The OB that produced the CHoCH becomes the entry zone.
       e. Place limit at OB (OTE depth). SL = sweep extreme + ATR buffer.
          TP1 = nearest opposing LTF FVG; TP2 = HTF liquidity target.
       f. Cancel after entry_ttl_bars or if HTF bias flips.

Signals are emitted only on the bar that arms the trade, not on every bar.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..config import RiskConfig, StrategyConfig
from ..core.types import FVG, OrderBlock, Signal, Trend
from ..smc.fvg import find_fvgs
from ..smc.liquidity import find_liquidity_pools
from ..smc.order_blocks import find_order_blocks, ob_entry_price, update_mitigation
from ..smc.structure import classify_structure
from ..smc.sweeps import detect_sweeps
from ..smc.swings import detect_swings
from ..utils.funding import in_funding_blackout
from .base import Strategy
from .context import SymbolContext

log = logging.getLogger(__name__)


def _atr(df: pd.DataFrame, period: int) -> float:
    if len(df) < period + 1:
        return 0.0
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    c = df["close"].to_numpy()
    prev_close = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum.reduce([h - l, np.abs(h - prev_close), np.abs(l - prev_close)])
    return float(tr[-period:].mean())


def _nearest_opposing_pool(pools, bias: Trend, ref_price: float) -> float | None:
    if bias == "up":
        # target = nearest sell-side liquidity (untapped high pool above price)
        cands = [p for p in pools if p.is_high and not p.swept and p.price > ref_price]
        if not cands:
            return None
        return min(cands, key=lambda p: p.price - ref_price).price
    if bias == "down":
        cands = [p for p in pools if (not p.is_high) and not p.swept and p.price < ref_price]
        if not cands:
            return None
        return max(cands, key=lambda p: p.price - ref_price).price
    return None


def _nearest_opposing_fvg(fvgs: list[FVG], side: str, ref_price: float) -> float | None:
    """For a long entry, nearest unfilled bearish FVG above ref_price (and vice-versa)."""
    if side == "long":
        cands = [g for g in fvgs if g.side == "short" and not g.filled and g.bottom > ref_price]
        if not cands:
            return None
        return min(cands, key=lambda g: g.bottom - ref_price).bottom
    cands = [g for g in fvgs if g.side == "long" and not g.filled and g.top < ref_price]
    if not cands:
        return None
    return max(cands, key=lambda g: g.top - ref_price).top


class SMCStrategy(Strategy):
    def __init__(self, strat: StrategyConfig, risk: RiskConfig):
        self.strat = strat
        self.risk = risk
        self._ctx: dict[str, SymbolContext] = {}

    def _ctx_for(self, symbol: str) -> SymbolContext:
        if symbol not in self._ctx:
            self._ctx[symbol] = SymbolContext()
        return self._ctx[symbol]

    def on_bar(
        self,
        symbol: str,
        ltf_df: pd.DataFrame,
        htf_df: pd.DataFrame,
    ) -> list[Signal]:
        if len(ltf_df) < 30 or len(htf_df) < 30:
            return []

        ctx = self._ctx_for(symbol)
        last_ts = int(ltf_df["ts"].iloc[-1])
        last_close = float(ltf_df["close"].iloc[-1])

        # Funding blackout
        if in_funding_blackout(last_ts, self.risk.funding_blackout_minutes):
            return []

        # 1. HTF bias
        htf_state = classify_structure(htf_df, self.strat.swing_left, self.strat.swing_right)
        prev_bias = ctx.htf_bias
        ctx.htf_bias = htf_state.trend

        # If HTF bias flipped, reset LTF state
        if ctx.htf_bias not in (prev_bias, "none"):
            ctx.reset()

        # 2. HTF target liquidity
        htf_swings = detect_swings(htf_df, self.strat.swing_left, self.strat.swing_right)
        htf_pools = find_liquidity_pools(
            htf_swings,
            self.strat.liquidity_tolerance_bps,
            self.strat.liquidity_min_touches,
        )
        ctx.htf_target_price = _nearest_opposing_pool(htf_pools, ctx.htf_bias, last_close)

        if ctx.htf_bias == "none" or ctx.htf_target_price is None:
            return []

        # 3. LTF SMC
        ltf_swings = detect_swings(ltf_df, self.strat.swing_left, self.strat.swing_right)
        ltf_pools = find_liquidity_pools(
            ltf_swings,
            self.strat.liquidity_tolerance_bps,
            self.strat.liquidity_min_touches,
        )
        ltf_sweeps = detect_sweeps(ltf_df, ltf_pools)
        ltf_struct = classify_structure(ltf_df, self.strat.swing_left, self.strat.swing_right)
        ltf_obs = find_order_blocks(ltf_df, ltf_struct.events)
        update_mitigation(ltf_obs, ltf_df)
        ltf_fvgs = find_fvgs(ltf_df, self.strat.fvg_min_size_bps)

        # 4. State machine
        # Look at the most recent sweep aligned with bias and not yet used.
        for sw in ltf_sweeps:
            if sw.idx in ctx.sweeps_used:
                continue
            aligned = (ctx.htf_bias == "up" and not sw.is_high) or (
                ctx.htf_bias == "down" and sw.is_high
            )
            if not aligned:
                continue
            if ctx.last_sweep is None or sw.idx > ctx.last_sweep.idx:
                ctx.last_sweep = sw
                ctx.sweep_seen_at_idx = len(ltf_df) - 1
                ctx.state = "waiting_choch"

        if ctx.state != "waiting_choch" or ctx.last_sweep is None:
            return []

        # Look for an LTF CHoCH in HTF direction *after* the sweep
        wanted = "CHOCH_UP" if ctx.htf_bias == "up" else "CHOCH_DOWN"
        choch = None
        for ev in ltf_struct.events:
            if ev.idx <= ctx.last_sweep.idx:
                continue
            if ev.event == wanted:
                choch = ev
                break
        if choch is None:
            # If too many bars elapsed since sweep without CHoCH, reset.
            if (len(ltf_df) - 1 - ctx.sweep_seen_at_idx) > self.strat.entry_ttl_bars * 2:
                ctx.reset()
            return []

        # Find OB associated with this CHoCH
        ob: OrderBlock | None = None
        for cand in ltf_obs:
            if cand.idx >= choch.idx:
                continue
            if cand.mitigated:
                continue
            if cand.idx in ctx.obs_used:
                continue
            wanted_side = "long" if ctx.htf_bias == "up" else "short"
            if cand.side != wanted_side:
                continue
            # pick the one closest to the CHoCH (most recent before)
            if ob is None or cand.idx > ob.idx:
                ob = cand
        if ob is None:
            return []

        # Build the signal
        side = "long" if ctx.htf_bias == "up" else "short"
        entry = ob_entry_price(ob, self.strat.ote_depth)

        atr = _atr(ltf_df, self.risk.sl_atr_period)
        sl_buffer = max(atr * self.risk.sl_atr_mult, last_close * self.risk.sl_buffer_bps / 1e4)

        if side == "long":
            sl = ctx.last_sweep.extreme - sl_buffer
        else:
            sl = ctx.last_sweep.extreme + sl_buffer

        # TP1 = nearest opposing LTF FVG; TP2 = HTF liquidity target
        tp1 = _nearest_opposing_fvg(ltf_fvgs, side, entry)
        tp2 = ctx.htf_target_price
        if tp1 is None:
            tp1 = tp2  # fall back to HTF target if no FVG

        # sanity: SL must be on the correct side of entry
        if (side == "long" and sl >= entry) or (side == "short" and sl <= entry):
            return []
        # sanity: TP must be on the correct side
        if (side == "long" and tp1 <= entry) or (side == "short" and tp1 >= entry):
            return []

        ctx.armed_ob = ob
        ctx.armed_at_ltf_idx = len(ltf_df) - 1
        ctx.state = "armed"
        ctx.obs_used.add(ob.idx)
        ctx.sweeps_used.add(ctx.last_sweep.idx)

        sig = Signal(
            side=side,
            entry=float(entry),
            stop_loss=float(sl),
            take_profit_1=float(tp1),
            take_profit_2=float(tp2) if tp2 is not None and tp2 != tp1 else None,
            reason=f"smc_mtf:{ctx.htf_bias}_bias+sweep+choch+ob",
            htf_bias=ctx.htf_bias,
            ob=ob,
            sweep=ctx.last_sweep,
            ts=last_ts,
        )
        ctx.last_signal_ts = last_ts
        # After arming, return to idle for the *next* setup hunt; broker handles fill/cancel.
        ctx.reset()
        log.info(
            "SIGNAL %s %s entry=%.4f sl=%.4f tp1=%.4f tp2=%s",
            symbol, side, sig.entry, sig.stop_loss, sig.take_profit_1, sig.take_profit_2,
        )
        return [sig]
