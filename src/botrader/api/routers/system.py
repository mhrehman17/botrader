"""System endpoints: /healthz, /config, /killswitch."""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ... import __version__
from ..auth import require_token
from ..runtime import get_runtime
from ..schemas import ConfigOut, ConfigPatch, Health, KillSwitchOut
from ..state import get_state

router = APIRouter()


@router.get("/healthz", response_model=Health)
def healthz(_: None = Depends(require_token)) -> Health:
    s = get_state()
    return Health(
        ok=True,
        mode=s.mode,
        running=s.running,
        started_at=s.started_at,
        version=__version__,
    )


_PATCHABLE_RISK = {
    "risk_pct_per_trade", "max_concurrent_positions", "max_leverage",
    "daily_loss_kill_pct", "max_drawdown_kill_pct",
    "sl_atr_period", "sl_atr_mult", "sl_buffer_bps", "trail_atr_mult",
    "funding_blackout_minutes", "funding_abs_cap",
}
_PATCHABLE_STRATEGY = {
    "swing_left", "swing_right", "fvg_min_size_bps", "liquidity_tolerance_bps",
    "liquidity_min_touches", "entry_ttl_bars", "partial_tp_pct", "ote_depth",
    "htf_lookback_bars", "ltf_lookback_bars",
}


def _redact(cfg) -> dict[str, Any]:
    return {
        "mode": cfg.mode,
        "symbols": list(cfg.symbols),
        "timeframes": {"htf": cfg.timeframes.htf, "ltf": cfg.timeframes.ltf},
        "strategy": cfg.strategy.model_dump(),
        "risk": cfg.risk.model_dump(),
        "exchange": {
            "id": cfg.exchange.id,
            "testnet": cfg.exchange.testnet,
            "api_key": "••••••••" if cfg.exchange.api_key else "",
            "api_secret": "••••••••" if cfg.exchange.api_secret else "",
        },
    }


@router.get("/config", response_model=ConfigOut)
def get_config(_: None = Depends(require_token)) -> ConfigOut:
    rt = get_runtime()
    return ConfigOut(**_redact(rt.cfg))


@router.put("/config", response_model=ConfigOut)
def patch_config(patch: ConfigPatch, _: None = Depends(require_token)) -> ConfigOut:
    rt = get_runtime()
    state = get_state()
    is_locked = state.mode == "mainnet" and state.running
    if is_locked:
        raise HTTPException(
            status_code=403,
            detail="Stop the bot before changing config on mainnet.",
        )
    cfg = rt.cfg
    if patch.risk:
        for k, v in patch.risk.items():
            if k not in _PATCHABLE_RISK:
                raise HTTPException(status_code=400, detail=f"Field '{k}' is not patchable.")
            setattr(cfg.risk, k, v)
    if patch.strategy:
        for k, v in patch.strategy.items():
            if k not in _PATCHABLE_STRATEGY:
                raise HTTPException(status_code=400, detail=f"Field '{k}' is not patchable.")
            setattr(cfg.strategy, k, v)
    return ConfigOut(**_redact(cfg))


@router.get("/killswitch", response_model=KillSwitchOut)
def killswitch(_: None = Depends(require_token)) -> KillSwitchOut:
    s = get_state()
    ks = s.killswitch
    return KillSwitchOut(
        tripped=bool(ks.get("tripped")),
        reason=ks.get("reason", ""),
        peak_equity=float(ks.get("peak_equity") or 0.0),
        day_start_equity=float(ks.get("day_start_equity") or 0.0),
    )


@router.get("/server-info")
def server_info(_: None = Depends(require_token)) -> dict[str, Any]:
    """Capability flags the mobile app uses to gate UI affordances."""
    return {
        "allow_mainnet": os.environ.get("BOTRADER_ALLOW_MAINNET", "") == "1",
        "version": __version__,
    }
