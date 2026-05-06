"""/positions, /trades."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import require_token
from ..schemas import PositionOut, TradeOut
from ..state import get_state

router = APIRouter()


@router.get("/positions", response_model=list[PositionOut])
def positions(_: None = Depends(require_token)) -> list[PositionOut]:
    return [
        PositionOut(
            symbol=p.symbol, side=p.side, qty=p.qty,
            entry_price=p.entry_price, stop_loss=p.stop_loss, take_profit=p.take_profit,
            unrealized_pnl=p.unrealized_pnl, leverage=p.leverage, opened_ts=p.opened_ts,
        )
        for p in get_state().snapshot_positions()
    ]


@router.get("/trades", response_model=list[TradeOut])
def trades(limit: int = 50, _: None = Depends(require_token)) -> list[TradeOut]:
    return [
        TradeOut(
            symbol=t.symbol, side=t.side,
            entry_ts=t.entry_ts, exit_ts=t.exit_ts,
            entry_price=t.entry_price, exit_price=t.exit_price,
            qty=t.qty, pnl=t.pnl, fees=t.fees,
            r_multiple=t.r_multiple, reason=t.reason,
        )
        for t in get_state().snapshot_trades(limit=limit)
    ]
