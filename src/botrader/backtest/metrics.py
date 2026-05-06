"""Backtest metrics: Sharpe, Sortino, max DD, profit factor, expectancy."""
from __future__ import annotations

import numpy as np

from ..core.types import Equity, Trade


def _equity_returns(curve: list[Equity]) -> np.ndarray:
    if len(curve) < 2:
        return np.array([])
    eq = np.array([e.equity for e in curve], dtype=float)
    rets = np.diff(eq) / np.where(eq[:-1] == 0, 1, eq[:-1])
    return rets


def max_drawdown(curve: list[Equity]) -> float:
    if not curve:
        return 0.0
    eq = np.array([e.equity for e in curve], dtype=float)
    peaks = np.maximum.accumulate(eq)
    dd = (peaks - eq) / np.where(peaks == 0, 1, peaks)
    return float(dd.max()) if dd.size else 0.0


def sharpe(curve: list[Equity], periods_per_year: int = 365 * 24 * 12) -> float:
    """Naive Sharpe from equity-curve returns; periods_per_year defaults to 5m bars."""
    rets = _equity_returns(curve)
    if rets.size < 2:
        return 0.0
    sd = rets.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(rets.mean() / sd * np.sqrt(periods_per_year))


def sortino(curve: list[Equity], periods_per_year: int = 365 * 24 * 12) -> float:
    rets = _equity_returns(curve)
    if rets.size < 2:
        return 0.0
    downside = rets[rets < 0]
    if downside.size == 0:
        return float("inf")
    sd = downside.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(rets.mean() / sd * np.sqrt(periods_per_year))


def trade_stats(trades: list[Trade]) -> dict[str, float]:
    n = len(trades)
    if n == 0:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "avg_r": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
        }
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    gp = sum(t.pnl for t in wins)
    gl = -sum(t.pnl for t in losses)
    return {
        "trades": float(n),
        "win_rate": len(wins) / n,
        "profit_factor": (gp / gl) if gl > 0 else float("inf"),
        "expectancy": sum(t.pnl for t in trades) / n,
        "avg_r": sum(t.r_multiple for t in trades) / n,
        "gross_profit": gp,
        "gross_loss": gl,
    }


def all_metrics(curve: list[Equity], trades: list[Trade]) -> dict[str, float]:
    out = {
        "max_drawdown": max_drawdown(curve),
        "sharpe": sharpe(curve),
        "sortino": sortino(curve),
        "final_equity": curve[-1].equity if curve else 0.0,
        "initial_equity": curve[0].equity if curve else 0.0,
    }
    out["total_return_pct"] = (
        (out["final_equity"] / out["initial_equity"] - 1) * 100
        if out["initial_equity"] > 0 else 0.0
    )
    out.update(trade_stats(trades))
    return out
