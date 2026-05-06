"""Drawdown-aware sizing: shrink risk after a losing streak, reset on a win."""
from __future__ import annotations

from dataclasses import dataclass

from botrader.risk.sizing import consecutive_losses, dd_risk_factor


@dataclass
class _T:
    pnl: float


def test_consecutive_losses_counts_trailing_streak():
    trades = [_T(1.0), _T(-1.0), _T(-1.0), _T(-1.0)]
    assert consecutive_losses(trades) == 3


def test_consecutive_losses_resets_on_win():
    trades = [_T(-1.0), _T(-1.0), _T(2.0), _T(-1.0)]
    assert consecutive_losses(trades) == 1


def test_consecutive_losses_empty_is_zero():
    assert consecutive_losses([]) == 0


def test_dd_factor_is_one_when_disabled():
    # multiplier 1.0 disables
    assert dd_risk_factor([_T(-1.0)] * 10, loss_streak=3, multiplier=1.0) == 1.0
    # loss_streak 0 disables
    assert dd_risk_factor([_T(-1.0)] * 10, loss_streak=0, multiplier=0.5) == 1.0


def test_dd_factor_kicks_in_at_threshold():
    # 2 losses, threshold 3 -> still full risk
    assert dd_risk_factor([_T(-1.0), _T(-1.0)], 3, 0.5) == 1.0
    # 3 losses -> halved
    assert dd_risk_factor([_T(-1.0), _T(-1.0), _T(-1.0)], 3, 0.5) == 0.5
    # 5 losses -> still halved (no further reduction)
    assert dd_risk_factor([_T(-1.0)] * 5, 3, 0.5) == 0.5


def test_dd_factor_resets_on_winning_trade():
    # 3 losses then a win -> back to full risk
    trades = [_T(-1.0), _T(-1.0), _T(-1.0), _T(2.0)]
    assert dd_risk_factor(trades, 3, 0.5) == 1.0


def test_breakeven_counts_as_loss_for_streak():
    # pnl == 0 (e.g., breakeven SL after TP1) should count toward the streak
    trades = [_T(-1.0), _T(0.0), _T(-1.0)]
    assert consecutive_losses(trades) == 3
    assert dd_risk_factor(trades, 3, 0.5) == 0.5
