"""/credentials — list, upsert, verify, delete exchange API keys.

The route handlers never return plaintext secrets. They only persist them
encrypted via `secrets_store`.
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from .. import secrets_store
from ..auth import require_token
from ..schemas import CredentialPublic, CredentialUpsert, CredentialVerify
from ..state import get_state

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/credentials", response_model=list[CredentialPublic])
def list_credentials(_: None = Depends(require_token)) -> list[CredentialPublic]:
    return [CredentialPublic(**v) for v in secrets_store.public_view_all()]


@router.put("/credentials/{exchange_id}", response_model=CredentialPublic)
def upsert(
    exchange_id: str, body: CredentialUpsert, _: None = Depends(require_token),
) -> CredentialPublic:
    if not body.api_key or not body.api_secret:
        raise HTTPException(status_code=400, detail="api_key and api_secret are required.")
    secrets_store.upsert(secrets_store.Credential(
        exchange_id=exchange_id,
        api_key=body.api_key,
        api_secret=body.api_secret,
        testnet=body.testnet,
        label=body.label,
        options=body.options,
        created_at=int(time.time()),
    ))
    view = secrets_store.public_view(exchange_id)
    if view is None:
        raise HTTPException(status_code=500, detail="Failed to persist credential.")
    return CredentialPublic(**view)


@router.delete("/credentials/{exchange_id}")
def delete(exchange_id: str, _: None = Depends(require_token)) -> dict:
    state = get_state()
    if state.running and state.mode in ("testnet", "mainnet"):
        # don't yank credentials out from under a running live broker
        raise HTTPException(
            status_code=409,
            detail="Stop the bot or switch to paper before deleting live credentials.",
        )
    ok = secrets_store.delete(exchange_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"No credential for {exchange_id}.")
    return {"ok": True}


@router.post("/credentials/{exchange_id}/verify", response_model=CredentialVerify)
def verify(exchange_id: str, _: None = Depends(require_token)) -> CredentialVerify:
    cred = secrets_store.load_for(exchange_id)
    if cred is None:
        raise HTTPException(status_code=404, detail=f"No credential for {exchange_id}.")
    try:
        import ccxt  # noqa: PLC0415
        klass = getattr(ccxt, exchange_id, None)
        if klass is None:
            raise ValueError(f"Unknown exchange id: {exchange_id}")
        ex = klass({
            "apiKey": cred.api_key,
            "secret": cred.api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "swap", **cred.options},
        })
        if cred.testnet and hasattr(ex, "set_sandbox_mode"):
            ex.set_sandbox_mode(True)
        ex.load_markets()
        bal = ex.fetch_balance()
        info = bal.get("info", {})
        secrets_store.mark_verified(exchange_id)
        return CredentialVerify(
            ok=True, error=None,
            account_type=str(info.get("accountType") or info.get("permissions") or "ok"),
        )
    except Exception as e:  # noqa: BLE001
        return CredentialVerify(ok=False, error=str(e)[:200], account_type=None)
