"""/scan: per-symbol SMC state."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import require_token
from ..schemas import ScanRowOut
from ..state import get_state

router = APIRouter()


@router.get("/scan", response_model=list[ScanRowOut])
def scan(_: None = Depends(require_token)) -> list[ScanRowOut]:
    return [
        ScanRowOut(
            symbol=r.symbol, bias=r.bias, state=r.state,
            target_price=r.target_price, last_close=r.last_close, ts=r.ts,
        )
        for r in get_state().snapshot_scan()
    ]
