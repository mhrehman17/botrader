"""Mode dispatcher for backtest / paper / live."""
from __future__ import annotations

from pathlib import Path

from ..config import BotConfig
from ..core.types import BacktestResult


def run_backtest(cfg: BotConfig, run_dir: Path) -> BacktestResult:
    from ..backtest.engine import run_backtest as _run
    return _run(cfg, run_dir)
