"""Backtest reporting: trades.csv, metrics.json, equity_curve.png."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from ..core.types import BacktestResult

log = logging.getLogger(__name__)


def write_report(result: BacktestResult, run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)

    # trades.csv
    trades_path = run_dir / "trades.csv"
    if result.trades:
        pd.DataFrame([asdict(t) for t in result.trades]).to_csv(trades_path, index=False)
    else:
        trades_path.write_text("symbol,side,entry_ts,exit_ts,entry_price,exit_price,qty,pnl,fees,r_multiple,reason\n")

    # equity_curve.csv
    eq_path = run_dir / "equity_curve.csv"
    pd.DataFrame([asdict(e) for e in result.equity_curve]).to_csv(eq_path, index=False)

    # metrics.json
    (run_dir / "metrics.json").write_text(json.dumps(result.metrics, indent=2, default=float))

    # equity_curve.png (best-effort; matplotlib may be missing in some envs)
    try:
        import matplotlib  # noqa: PLC0415
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: PLC0415

        if result.equity_curve:
            xs = [e.ts for e in result.equity_curve]
            ys = [e.equity for e in result.equity_curve]
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(pd.to_datetime(xs, unit="ms"), ys, color="#0a84ff")
            ax.set_title("Equity Curve")
            ax.set_ylabel("Equity (quote ccy)")
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            fig.savefig(run_dir / "equity_curve.png", dpi=110)
            plt.close(fig)
    except Exception as e:  # noqa: BLE001
        log.warning("Could not render equity curve: %s", e)


def regenerate_report(run_dir: Path) -> None:
    """Re-render plots/metrics from trades.csv + equity_curve.csv if present."""
    log.info("Regenerating report from %s", run_dir)
    # Minimal stub — left for future expansion.
    if not (run_dir / "metrics.json").exists():
        log.warning("No metrics.json found in %s", run_dir)
