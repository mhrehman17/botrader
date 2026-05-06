"""Bearer-token auth middleware.

Reads `BOTRADER_API_TOKEN` from env. If unset, the API refuses to start.
Use `openssl rand -hex 16` to generate a token for personal use.
"""
from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException, status

_AUTH_DOC = "Authorization: Bearer <token>"


def require_token(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("BOTRADER_API_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server misconfigured: BOTRADER_API_TOKEN is not set.",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing {_AUTH_DOC}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    presented = authorization[len("Bearer ") :].strip()
    # constant-time compare to avoid timing oracle
    if not hmac.compare_digest(presented, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
