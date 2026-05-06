"""Run several backtest variants on the same cached data and print a side-by-side
metrics table.

Reports — in order of decreasing usefulness for evaluating a strategy:

  expectancy ($/trade)   <-- the actual measure of edge
  profit_factor          <-- gross_win / gross_loss
  total_return_pct
  max_drawdown
  sharpe / sortino
  win_rate               <-- LAST. High win-rate ≠ profitable.
  avg_r (mean R-multiple)
  trades                 <-- sample size; <30 = noise
  R-distribution stats: best, worst, std

Usage::

    python scripts/compare_variants.py [config-path]

By default uses configs/backtest.yaml and assumes the parquet cache is already
populated.  The variants exercised below are illustrative; tweak the
``VARIANTS`` list to compare your own configs.

This script does NOT pretend to validate live profitability.  Use it to compare
the *relative* effect of changes on the same cached data.  For real validation
you need walk-forward on real candles, on multiple symbols.
"""
from __future__ import annotations

import copy
import math
import statistics
import sys
from pathlib import Path
from typing import Any

from botrader.backtest.engine import run_backtest
from botrader.config import load_config

VARIANTS: list[tuple[str, dict[str, Any]]] = [
    ("legacy_no_gates",  {"strategy.min_rr_to_tp1": 0.0, "strategy.max_sl_atr_mult": 999.0}),
    ("min_rr_1.0",       {"strategy.min_rr_to_tp1": 1.0, "strategy.max_sl_atr_mult": 999.0}),
    ("min_rr_1.5",       {"strategy.min_rr_to_tp1": 1.5, "strategy.max_sl_atr_mult": 999.0}),
    ("max_sl_atr_2",     {"strategy.min_rr_to_tp1": 0.0, "strategy.max_sl_atr_mult": 2.0}),
    ("rr+sl_gates",      {"strategy.min_rr_to_tp1": 1.0, "strategy.max_sl_atr_mult": 2.5}),
    ("rr+sl+dd0.5",      {
        "strategy.min_rr_to_tp1": 1.0,
        "strategy.max_sl_atr_mult": 2.5,
        "risk.dd_loss_streak": 3,
        "risk.dd_risk_multiplier": 0.5,
    }),
    ("rr+sl+dd+trail",   {
        "strategy.min_rr_to_tp1": 1.0,
        "strategy.max_sl_atr_mult": 2.5,
        "risk.dd_loss_streak": 3,
        "risk.dd_risk_multiplier": 0.5,
        "risk.trail_atr_mult": 1.5,
    }),
]


def _set(cfg, dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    obj = cfg
    for p in parts[:-1]:
        obj = getattr(obj, p)
    setattr(obj, parts[-1], value)


def _summarize(name: str, result) -> dict[str, Any]:
    m = result.metrics
    rs = [t.r_multiple for t in result.trades]
    return {
        "variant": name,
        "trades": int(m.get("trades", 0)),
        "expectancy": m.get("expectancy", 0.0),
        "profit_factor": m.get("profit_factor", 0.0),
        "total_return_pct": m.get("total_return_pct", 0.0),
        "max_drawdown": m.get("max_drawdown", 0.0),
        "sharpe": m.get("sharpe", 0.0),
        "sortino": m.get("sortino", 0.0),
        "win_rate": m.get("win_rate", 0.0),
        "avg_r": m.get("avg_r", 0.0),
        "best_r": max(rs, default=0.0),
        "worst_r": min(rs, default=0.0),
        "r_std": statistics.pstdev(rs) if len(rs) > 1 else 0.0,
    }


def _fmt(v: Any, kind: str) -> str:
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return "∞" if v > 0 else "-∞" if v < 0 else "nan"
    if kind == "pct":
        return f"{v:>+7.2f}%"
    if kind == "money":
        return f"{v:>+8.2f}"
    if kind == "ratio":
        return f"{v:>6.2f}"
    if kind == "int":
        return f"{int(v):>5d}"
    if kind == "frac":
        return f"{v * 100:>5.1f}%"
    return str(v)


def _print_table(rows: list[dict[str, Any]]) -> None:
    cols = [
        ("variant",          "name",  None,    16),
        ("trades",           "n",     "int",   5),
        ("expectancy",       "exp$",  "money", 9),
        ("profit_factor",    "PF",    "ratio", 7),
        ("total_return_pct", "ret%",  "pct",   8),
        ("max_drawdown",     "MDD",   "frac",  7),
        ("sharpe",           "sh",    "ratio", 7),
        ("sortino",          "sor",   "ratio", 7),
        ("win_rate",         "win%",  "frac",  7),
        ("avg_r",            "avgR",  "ratio", 7),
        ("best_r",           "+R",    "ratio", 7),
        ("worst_r",          "-R",    "ratio", 7),
        ("r_std",            "Rsd",   "ratio", 7),
    ]
    header = "  ".join(f"{label:>{w}}" for _, label, _, w in cols)
    print(header)
    print("-" * len(header))
    for r in rows:
        line = "  ".join(
            _fmt(r[k], kind) if kind else f"{r[k]:>{w}}"
            for k, _, kind, w in cols
        )
        print(line)


def main() -> None:
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("configs/backtest.yaml")
    base = load_config(cfg_path)
    rows = []
    for name, overrides in VARIANTS:
        cfg = copy.deepcopy(base)
        for dotted, value in overrides.items():
            _set(cfg, dotted, value)
        run_dir = Path("runs") / f"compare_{name}"
        result = run_backtest(cfg, run_dir)
        rows.append(_summarize(name, result))
    _print_table(rows)
    print()
    print("Reminder: high win-rate ≠ profitable. Read the `expectancy` and")
    print("`profit_factor` columns first. Sample size <30 (`n` column) is noise.")


if __name__ == "__main__":
    main()
