"""Swing-point (fractal) detection.

A bar `i` is a swing high iff its high is strictly greater than the max high in
the `left` bars before it AND in the `right` bars after it. Mirror for swing low.

Important: a swing is **only confirmed** once `right` bars have elapsed past it.
This is critical — using unconfirmed swings is a common source of lookahead bias
in SMC backtests. The strategy must filter `confirmed_at_idx <= current_idx`.
"""
from __future__ import annotations

import pandas as pd

from ..core.types import Swing, SwingKind


def detect_swings(df: pd.DataFrame, left: int = 2, right: int = 2) -> list[Swing]:
    """Return all confirmed swings in df with HH/HL/LH/LL labels.

    df must have columns: ts, high, low. Indexed 0..n-1.
    """
    if left < 1 or right < 1:
        raise ValueError("left and right must be >= 1")
    n = len(df)
    if n < left + right + 1:
        return []

    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    ts = df["ts"].to_numpy()

    swings: list[Swing] = []
    prev_high: float | None = None
    prev_low: float | None = None

    for i in range(left, n - right):
        h = highs[i]
        # strict > on the left, >= on the right would be too permissive; use strict >
        if h > highs[i - left:i].max() and h > highs[i + 1:i + right + 1].max():
            kind: SwingKind = "HH" if (prev_high is None or h > prev_high) else "LH"
            swings.append(Swing(idx=i, ts=int(ts[i]), price=float(h), kind=kind, is_high=True))
            prev_high = float(h)
            continue  # a bar can't be both swing high and swing low
        ll = lows[i]
        if ll < lows[i - left:i].min() and ll < lows[i + 1:i + right + 1].min():
            kind = "HL" if (prev_low is None or ll > prev_low) else "LL"
            swings.append(Swing(idx=i, ts=int(ts[i]), price=float(ll), kind=kind, is_high=False))
            prev_low = float(ll)

    return swings


def confirmation_idx(swing: Swing, right: int) -> int:
    """Bar index at which `swing` becomes known (i.e., confirmed)."""
    return swing.idx + right
