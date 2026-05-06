"""Position sizing.

For a linear-quoted perpetual (USDT-margined): qty (in base) is computed so
that a stop-out costs `risk_pct * equity`.

    risk_dollars = equity * risk_pct
    qty = risk_dollars / |entry - stop|

We then floor to the contract step and cap by leverage.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ContractSpec:
    qty_step: float = 0.001       # min increment in base qty
    min_qty: float = 0.001
    price_step: float = 0.1
    contract_size: float = 1.0    # base units per contract (1 for linear)


def floor_to_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    return (int(value / step)) * step


def consecutive_losses(trades: list) -> int:
    """Count the trailing streak of losing trades. A trade with pnl <= 0 is a loss."""
    n = 0
    for t in reversed(trades):
        if getattr(t, "pnl", 0.0) <= 0:
            n += 1
        else:
            break
    return n


def dd_risk_factor(trades: list, loss_streak: int, multiplier: float) -> float:
    """Drawdown-aware sizing factor.

    Returns `multiplier` once the trailing streak of losing trades reaches
    `loss_streak`; otherwise returns 1.0. A winning trade fully resets.
    multiplier == 1.0 disables the feature.
    """
    if multiplier >= 1.0 or loss_streak <= 0:
        return 1.0
    return multiplier if consecutive_losses(trades) >= loss_streak else 1.0


def size_position(
    equity: float,
    risk_pct: float,
    entry: float,
    stop_loss: float,
    spec: ContractSpec,
    max_leverage: float = 5.0,
) -> float:
    """Return qty in base units. Returns 0 if risk distance is zero or below min."""
    risk_dollars = equity * risk_pct
    sl_distance = abs(entry - stop_loss)
    if sl_distance <= 0:
        return 0.0
    raw_qty = risk_dollars / sl_distance
    # cap by leverage: notional = qty * entry <= equity * max_leverage
    max_notional = equity * max_leverage
    max_qty_by_lev = max_notional / entry if entry > 0 else 0
    qty = min(raw_qty, max_qty_by_lev)
    qty = floor_to_step(qty, spec.qty_step)
    if qty < spec.min_qty:
        return 0.0
    return qty
