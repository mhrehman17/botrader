"""Per-symbol strategy context: HTF bias + LTF state machine.

State machine for LTF (per HTF bias direction):

  IDLE
    -> waiting_for_sweep  (when HTF bias != none and target liquidity exists)

  WAITING_FOR_SWEEP
    -> waiting_for_choch  (when LTF sweep aligned with HTF bias is detected)

  WAITING_FOR_CHOCH
    -> armed              (when LTF CHoCH in HTF direction occurs and an OB is found)
    -> idle               (if too many bars elapse without CHoCH)

  ARMED
    -> in_trade           (when limit fills) -- handled outside this class
    -> idle               (if entry_ttl_bars elapse without fill, or HTF bias flips)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..core.types import OrderBlock, Sweep, Trend


@dataclass
class SymbolContext:
    htf_bias: Trend = "none"
    state: str = "idle"            # idle | waiting_sweep | waiting_choch | armed
    last_sweep: Sweep | None = None
    sweep_seen_at_idx: int = -1
    armed_ob: OrderBlock | None = None
    armed_at_ltf_idx: int = -1
    htf_target_price: float | None = None
    last_signal_ts: int = 0

    # bookkeeping
    sweeps_used: set[int] = field(default_factory=set)
    obs_used: set[int] = field(default_factory=set)

    def reset(self) -> None:
        self.state = "idle"
        self.last_sweep = None
        self.sweep_seen_at_idx = -1
        self.armed_ob = None
        self.armed_at_ltf_idx = -1
