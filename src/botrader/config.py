"""Configuration models and YAML loader.

Configs support `extends: <path>` for inheritance. Env-var substitution uses
`${VAR}` syntax inside strings; we resolve these at load time with `os.environ`.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

Mode = Literal["backtest", "paper", "testnet", "mainnet"]


class ExchangeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = "binanceusdm"
    testnet: bool = True
    api_key: str = ""
    api_secret: str = ""
    options: dict[str, Any] = Field(default_factory=dict)


class TimeframesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    htf: str = "1h"
    ltf: str = "5m"


class StrategyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    swing_left: int = 2
    swing_right: int = 2
    fvg_min_size_bps: float = 3.0
    liquidity_tolerance_bps: float = 5.0
    liquidity_min_touches: int = 2
    entry_ttl_bars: int = 12
    partial_tp_pct: float = 0.5
    ote_depth: float = 0.5
    htf_lookback_bars: int = 500
    ltf_lookback_bars: int = 500
    # Reject signals where TP1 is too close to entry vs the SL distance.
    # 1.0 = TP1 distance must equal at least one SL-distance (1R). Default
    # 1.0 keeps the floor at "break-even after fees on a typical winner".
    min_rr_to_tp1: float = 1.0
    # Cap the SL distance to N×ATR(sl_atr_period); rejects entries with
    # impractically wide stops (which give terrible R:R).
    max_sl_atr_mult: float = 4.0


class RiskConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    risk_pct_per_trade: float = 0.005
    max_concurrent_positions: int = 2
    max_leverage: float = 5.0
    daily_loss_kill_pct: float = 0.03
    max_drawdown_kill_pct: float = 0.10
    sl_atr_period: int = 14
    sl_atr_mult: float = 1.0
    sl_buffer_bps: float = 2.0
    trail_atr_mult: float = 0.0  # 0 disables trailing; e.g. 1.5 = trail by 1.5*ATR(14) past 1R
    funding_blackout_minutes: int = 5
    funding_abs_cap: float = 0.001
    # Drawdown-aware sizing. After `dd_loss_streak` consecutive losing
    # trades, multiply per-trade risk by `dd_risk_multiplier`. Reset on
    # a winning trade. 1.0 disables.
    dd_loss_streak: int = 3
    dd_risk_multiplier: float = 1.0


class BacktestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: date = date(2024, 1, 1)
    end: date = date(2024, 12, 31)
    fee_bps: float = 4.0
    slippage_bps: float = 2.0
    initial_equity: float = 10_000.0

    @field_validator("start", "end", mode="before")
    @classmethod
    def _parse_date(cls, v: Any) -> Any:
        if isinstance(v, str):
            return datetime.strptime(v, "%Y-%m-%d").date()
        return v


class DataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cache_dir: str = ".cache/ohlcv"


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: str = "INFO"


class BotConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Mode = "backtest"
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    symbols: list[str] = Field(default_factory=lambda: ["BTC/USDT:USDT"])
    timeframes: TimeframesConfig = Field(default_factory=TimeframesConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _substitute_env(obj: Any) -> Any:
    if isinstance(obj, str):
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), obj)
    if isinstance(obj, dict):
        return {k: _substitute_env(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute_env(x) for x in obj]
    return obj


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_with_extends(path: Path, _seen: set[Path] | None = None) -> dict[str, Any]:
    _seen = _seen or set()
    path = path.resolve()
    if path in _seen:
        raise ValueError(f"Circular extends detected at {path}")
    _seen.add(path)
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    extends = raw.pop("extends", None)
    if extends:
        parent_path = (path.parent / extends).resolve()
        parent = _load_with_extends(parent_path, _seen)
        return _deep_merge(parent, raw)
    return raw


def load_config(path: str | Path) -> BotConfig:
    """Load and validate a YAML config. Supports `extends:` and `${ENV}` substitution."""
    load_dotenv(override=False)  # load .env if present
    p = Path(path)
    raw = _load_with_extends(p)
    raw = _substitute_env(raw)
    return BotConfig.model_validate(raw)
