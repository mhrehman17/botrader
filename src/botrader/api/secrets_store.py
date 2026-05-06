"""Encrypted-at-rest exchange-credentials vault.

File format: a JSON object mapping `exchange_id` -> a record. Each record
stores the api_key and api_secret as Fernet-encrypted base64 strings, plus
metadata (testnet flag, label, timestamps).

Encryption key derivation:
- Source: `BOTRADER_MASTER_KEY` env var (any non-empty string).
- Derivation: `Fernet(base64.urlsafe_b64encode(SHA256(BOTRADER_MASTER_KEY).digest()))`.
  This is intentional: callers can rotate the env var to invalidate stored
  credentials without touching the file.

File path:
- Default `~/.botrader/credentials.enc`. Override with `BOTRADER_CREDENTIALS_PATH`.
- Created with `0600` mode (owner read/write only). Atomic write via tmp+rename.

Threading: callers should hold a process-wide lock when mutating; this module
uses a module-level `threading.Lock`.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger(__name__)

_LOCK = threading.Lock()
_DEFAULT_PATH = Path.home() / ".botrader" / "credentials.enc"


def _path() -> Path:
    return Path(os.environ.get("BOTRADER_CREDENTIALS_PATH", str(_DEFAULT_PATH)))


def _fernet() -> Fernet:
    raw = os.environ.get("BOTRADER_MASTER_KEY", "")
    if not raw:
        raise RuntimeError(
            "BOTRADER_MASTER_KEY is not set. Set it to any non-empty string "
            "(e.g. `openssl rand -hex 32`) to enable credential storage."
        )
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


@dataclass
class Credential:
    exchange_id: str
    api_key: str
    api_secret: str
    testnet: bool = True
    label: str = ""
    options: dict[str, Any] = field(default_factory=dict)
    created_at: int = 0
    last_verified_at: int | None = None


def _read_raw() -> dict[str, dict[str, Any]]:
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Corrupt credentials file at {p}: {e}") from e


def _atomic_write(data: dict[str, dict[str, Any]]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    # Open with restrictive mode from the start
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
        os.chmod(p, 0o600)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def list_ids() -> list[str]:
    with _LOCK:
        return sorted(_read_raw().keys())


def has(exchange_id: str) -> bool:
    with _LOCK:
        return exchange_id in _read_raw()


def public_view(exchange_id: str) -> dict[str, Any] | None:
    """Return non-secret metadata for one credential, or None if missing."""
    with _LOCK:
        rec = _read_raw().get(exchange_id)
        if rec is None:
            return None
        return {
            "id": exchange_id,
            "has_key": True,
            "label": rec.get("label", ""),
            "testnet": bool(rec.get("testnet", True)),
            "created_at": rec.get("created_at"),
            "last_verified_at": rec.get("last_verified_at"),
        }


def public_view_all() -> list[dict[str, Any]]:
    with _LOCK:
        out = []
        for k, rec in sorted(_read_raw().items()):
            out.append({
                "id": k,
                "has_key": True,
                "label": rec.get("label", ""),
                "testnet": bool(rec.get("testnet", True)),
                "created_at": rec.get("created_at"),
                "last_verified_at": rec.get("last_verified_at"),
            })
        return out


def upsert(cred: Credential) -> None:
    """Encrypt and persist a credential. Does not verify connectivity."""
    f = _fernet()
    enc_key = f.encrypt(cred.api_key.encode("utf-8")).decode("ascii")
    enc_sec = f.encrypt(cred.api_secret.encode("utf-8")).decode("ascii")
    rec = {
        "api_key_enc": enc_key,
        "api_secret_enc": enc_sec,
        "testnet": bool(cred.testnet),
        "label": cred.label,
        "options": cred.options,
        "created_at": cred.created_at or int(time.time()),
        "last_verified_at": cred.last_verified_at,
    }
    with _LOCK:
        data = _read_raw()
        data[cred.exchange_id] = rec
        _atomic_write(data)


def load_for(exchange_id: str) -> Credential | None:
    """Load a credential and decrypt the secrets. **Returns plaintext** — only
    call from inside the server process when constructing a broker."""
    with _LOCK:
        rec = _read_raw().get(exchange_id)
    if rec is None:
        return None
    f = _fernet()
    try:
        api_key = f.decrypt(rec["api_key_enc"].encode("ascii")).decode("utf-8")
        api_secret = f.decrypt(rec["api_secret_enc"].encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        raise RuntimeError(
            f"Failed to decrypt credentials for {exchange_id}: wrong BOTRADER_MASTER_KEY?"
        ) from e
    return Credential(
        exchange_id=exchange_id,
        api_key=api_key,
        api_secret=api_secret,
        testnet=bool(rec.get("testnet", True)),
        label=rec.get("label", ""),
        options=rec.get("options", {}),
        created_at=int(rec.get("created_at", 0)),
        last_verified_at=rec.get("last_verified_at"),
    )


def delete(exchange_id: str) -> bool:
    with _LOCK:
        data = _read_raw()
        if exchange_id not in data:
            return False
        del data[exchange_id]
        _atomic_write(data)
        return True


def mark_verified(exchange_id: str) -> None:
    with _LOCK:
        data = _read_raw()
        if exchange_id in data:
            data[exchange_id]["last_verified_at"] = int(time.time())
            _atomic_write(data)
