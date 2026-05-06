"""/bot/start, /bot/stop, /bot/mode — bot lifecycle and mode-toggle."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_token
from ..runtime import get_runtime
from ..schemas import BotControlOut, ModeRequest
from ..state import get_state

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/bot/start", response_model=BotControlOut)
def start(_: None = Depends(require_token)) -> BotControlOut:
    rt = get_runtime()
    rt.start()
    s = get_state()
    return BotControlOut(ok=True, mode=s.mode, running=s.running, message="started")


@router.post("/bot/stop", response_model=BotControlOut)
def stop(_: None = Depends(require_token)) -> BotControlOut:
    rt = get_runtime()
    rt.stop("user")
    s = get_state()
    return BotControlOut(ok=True, mode=s.mode, running=s.running, message="stopped")


@router.post("/bot/mode", response_model=BotControlOut)
def switch_mode(req: ModeRequest, _: None = Depends(require_token)) -> BotControlOut:
    rt = get_runtime()
    try:
        rt.switch_mode(req.mode, exchange_id=req.exchange_id, confirm=req.confirm)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    s = get_state()
    return BotControlOut(
        ok=True, mode=s.mode, running=s.running,
        message=f"mode={req.mode}",
    )
