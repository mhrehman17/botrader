"""/candles?symbol=&tf=&limit=&overlays=1."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...smc.fvg import find_fvgs, update_fills
from ...smc.liquidity import find_liquidity_pools
from ...smc.order_blocks import find_order_blocks, update_mitigation
from ...smc.structure import classify_structure
from ...smc.sweeps import detect_sweeps
from ...smc.swings import detect_swings
from ..auth import require_token
from ..schemas import CandleOut, CandlesResponse, FvgOut, OrderBlockOut, SweepOut
from ..state import get_state

router = APIRouter()


@router.get("/candles", response_model=CandlesResponse)
def candles(
    symbol: str,
    tf: str,
    limit: int = 200,
    overlays: int = 1,
    _: None = Depends(require_token),
) -> CandlesResponse:
    df = get_state().snapshot_candles(symbol, tf)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No candles for {symbol} {tf}.")
    df = df.tail(max(limit, 50)).reset_index(drop=True)
    candles_out = [
        CandleOut(
            ts=int(r.ts), open=float(r.open), high=float(r.high),
            low=float(r.low), close=float(r.close), volume=float(r.volume),
        )
        for r in df.itertuples(index=False)
    ]
    overlays_out: dict[str, list] = {"order_blocks": [], "fvgs": [], "sweeps": []}
    if overlays:
        struct = classify_structure(df)
        obs = find_order_blocks(df, struct.events)
        update_mitigation(obs, df)
        fvgs = find_fvgs(df)
        update_fills(fvgs, df)
        swings = detect_swings(df)
        pools = find_liquidity_pools(swings)
        sweeps = detect_sweeps(df, pools)
        overlays_out["order_blocks"] = [
            OrderBlockOut(
                idx=ob.idx, ts=ob.ts, top=ob.top, bottom=ob.bottom,
                side=ob.side, mitigated=ob.mitigated,
            ).model_dump() for ob in obs
        ]
        overlays_out["fvgs"] = [
            FvgOut(
                idx=g.idx, ts=g.ts, top=g.top, bottom=g.bottom,
                side=g.side, filled=g.filled,
            ).model_dump() for g in fvgs
        ]
        overlays_out["sweeps"] = [
            SweepOut(
                idx=s.idx, ts=s.ts, pool_price=s.pool_price, is_high=s.is_high,
                extreme=s.extreme, close=s.close,
            ).model_dump() for s in sweeps
        ]
    return CandlesResponse(symbol=symbol, tf=tf, candles=candles_out, overlays=overlays_out)
