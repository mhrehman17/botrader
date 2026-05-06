"""Account: /equity, /equity-curve."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import require_token
from ..schemas import EquityPoint, EquitySnapshot
from ..state import get_state

router = APIRouter()


@router.get("/equity", response_model=EquitySnapshot)
def equity(_: None = Depends(require_token)) -> EquitySnapshot:
    s = get_state()
    curve = s.snapshot_equity()
    if not curve:
        return EquitySnapshot(
            equity=0.0, cash=0.0, upnl=0.0,
            daily_pnl=0.0, peak_equity=0.0, initial_equity=0.0,
        )
    initial = curve[0].equity
    last = curve[-1]
    peak = max((p.equity for p in curve), default=last.equity)
    # daily_pnl: equity now - day_start_equity (from killswitch)
    day_start = float(s.killswitch.get("day_start_equity") or initial)
    return EquitySnapshot(
        equity=last.equity, cash=last.cash, upnl=last.upnl or 0.0,
        daily_pnl=last.equity - day_start,
        peak_equity=peak, initial_equity=initial,
    )


@router.get("/equity-curve", response_model=list[EquityPoint])
def equity_curve(n: int = 200, _: None = Depends(require_token)) -> list[EquityPoint]:
    s = get_state()
    curve = s.snapshot_equity()
    if n > 0:
        curve = curve[-n:]
    return [EquityPoint(ts=p.ts, equity=p.equity, cash=p.cash, upnl=p.upnl or 0.0) for p in curve]
