"""End-to-end backtest pipeline test on synthetic OHLCV.

Generates a price series with a clear bullish setup pattern (range + sweep low + reversal),
caches it as parquet, and verifies the engine runs without exception and produces
artifacts (metrics.json, equity_curve.csv, trades.csv).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from botrader.backtest.engine import run_backtest
from botrader.config import (
    BacktestConfig,
    BotConfig,
    DataConfig,
    ExchangeConfig,
    LoggingConfig,
    RiskConfig,
    StrategyConfig,
    TimeframesConfig,
)
from botrader.data.ohlcv import cache_path, save_cache


def _make_synthetic_5m(n: int = 6000, start_price: float = 1000.0,
                       seed: int = 42) -> pd.DataFrame:
    """Random walk with deliberate liquidity sweeps every ~200 bars to create SMC patterns."""
    rng = np.random.default_rng(seed)
    ts0 = pd.Timestamp("2024-06-01", tz="UTC").value // 1_000_000
    step = 5 * 60 * 1000
    prices = [start_price]
    for i in range(1, n):
        drift = 0.0002 * np.sin(i / 200)  # gentle cycle
        shock = rng.normal(0, 0.0008)
        # inject sweep wicks every ~200 bars
        if i % 200 == 0:
            shock = -0.01 if (i // 200) % 2 == 0 else 0.01
        prices.append(prices[-1] * (1 + drift + shock))
    rows = []
    for i in range(n):
        c = prices[i]
        o = prices[i - 1] if i > 0 else c
        h = max(o, c) * (1 + abs(rng.normal(0, 0.0005)))
        l = min(o, c) * (1 - abs(rng.normal(0, 0.0005)))
        rows.append((ts0 + i * step, o, h, l, c, 100.0))
    return pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])


def test_backtest_runs_end_to_end(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    sym = "TEST/USDT:USDT"
    ex_id = "binanceusdm"

    df = _make_synthetic_5m()
    save_cache(df, cache_path(cache_dir, ex_id, sym, "5m"))

    cfg = BotConfig(
        mode="backtest",
        exchange=ExchangeConfig(id=ex_id, testnet=True, api_key="", api_secret=""),
        symbols=[sym],
        timeframes=TimeframesConfig(htf="1h", ltf="5m"),
        strategy=StrategyConfig(htf_lookback_bars=200, ltf_lookback_bars=200),
        risk=RiskConfig(
            risk_pct_per_trade=0.005,
            max_concurrent_positions=1,
            max_leverage=5,
            daily_loss_kill_pct=0.20,
            max_drawdown_kill_pct=0.50,
            funding_blackout_minutes=0,
        ),
        backtest=BacktestConfig(
            start=date(2024, 6, 1),
            end=date(2024, 6, 30),
            fee_bps=4,
            slippage_bps=2,
            initial_equity=10_000,
        ),
        data=DataConfig(cache_dir=str(cache_dir)),
        logging=LoggingConfig(level="WARNING"),
    )

    run_dir = tmp_path / "runs"
    result = run_backtest(cfg, run_dir)

    # invariants
    assert result.equity_curve, "expected non-empty equity curve"
    assert "max_drawdown" in result.metrics
    assert "sharpe" in result.metrics
    assert (run_dir / "metrics.json").exists()
    assert (run_dir / "trades.csv").exists()
    assert (run_dir / "equity_curve.csv").exists()
    # final equity is finite
    assert np.isfinite(result.equity_curve[-1].equity)


@pytest.mark.parametrize("seed", [1, 7, 13])
def test_backtest_no_exception_on_random_data(seed: int, tmp_path: Path):
    """Property test: random OHLCV must not raise."""
    cache_dir = tmp_path / "cache"
    sym = "TEST/USDT:USDT"
    df = _make_synthetic_5m(n=2000, seed=seed)
    save_cache(df, cache_path(cache_dir, "binanceusdm", sym, "5m"))

    cfg = BotConfig(
        mode="backtest",
        symbols=[sym],
        timeframes=TimeframesConfig(htf="1h", ltf="5m"),
        backtest=BacktestConfig(start=date(2024, 6, 1), end=date(2024, 6, 30),
                                initial_equity=10_000),
        data=DataConfig(cache_dir=str(cache_dir)),
        logging=LoggingConfig(level="WARNING"),
        risk=RiskConfig(funding_blackout_minutes=0,
                        daily_loss_kill_pct=0.5, max_drawdown_kill_pct=0.9),
    )
    result = run_backtest(cfg, tmp_path / f"runs_{seed}")
    assert result.equity_curve
