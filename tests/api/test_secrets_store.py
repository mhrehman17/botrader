"""Encrypted credential vault: round-trip, atomic write, mode 0600, key rotation refusal."""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from botrader.api import secrets_store


@pytest.fixture
def store_env(tmp_path: Path, monkeypatch):
    p = tmp_path / "creds.enc"
    monkeypatch.setenv("BOTRADER_CREDENTIALS_PATH", str(p))
    monkeypatch.setenv("BOTRADER_MASTER_KEY", "k1-test-master-key")
    yield p


def test_upsert_and_load_roundtrip(store_env: Path):
    cred = secrets_store.Credential(
        exchange_id="binanceusdm",
        api_key="AKID-XYZ",
        api_secret="SECRET-VALUE",
        testnet=True,
        label="testnet-1",
    )
    secrets_store.upsert(cred)
    assert secrets_store.has("binanceusdm")
    loaded = secrets_store.load_for("binanceusdm")
    assert loaded is not None
    assert loaded.api_key == "AKID-XYZ"
    assert loaded.api_secret == "SECRET-VALUE"
    assert loaded.testnet is True
    assert loaded.label == "testnet-1"
    assert loaded.created_at > 0


def test_public_view_never_returns_secrets(store_env: Path):
    cred = secrets_store.Credential(
        exchange_id="bybit",
        api_key="K",
        api_secret="S",
        testnet=True,
    )
    secrets_store.upsert(cred)
    view = secrets_store.public_view("bybit")
    assert view is not None
    assert "api_key" not in view
    assert "api_secret" not in view
    assert "api_key_enc" not in view
    assert "api_secret_enc" not in view
    assert view["has_key"] is True


def test_file_mode_is_0600(store_env: Path):
    cred = secrets_store.Credential(
        exchange_id="okx", api_key="K", api_secret="S", testnet=True,
    )
    secrets_store.upsert(cred)
    mode = os.stat(store_env).st_mode
    # only owner read+write, no group/other bits
    assert stat.S_IMODE(mode) == 0o600


def test_wrong_master_key_refuses_to_decrypt(store_env: Path, monkeypatch):
    cred = secrets_store.Credential(
        exchange_id="bybit", api_key="K", api_secret="S", testnet=True,
    )
    secrets_store.upsert(cred)
    # rotate the key
    monkeypatch.setenv("BOTRADER_MASTER_KEY", "different-key")
    with pytest.raises(RuntimeError, match="wrong BOTRADER_MASTER_KEY"):
        secrets_store.load_for("bybit")


def test_missing_master_key_raises_on_upsert(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BOTRADER_CREDENTIALS_PATH", str(tmp_path / "creds.enc"))
    monkeypatch.delenv("BOTRADER_MASTER_KEY", raising=False)
    with pytest.raises(RuntimeError, match="BOTRADER_MASTER_KEY is not set"):
        secrets_store.upsert(secrets_store.Credential(
            exchange_id="x", api_key="k", api_secret="s",
        ))


def test_delete(store_env: Path):
    secrets_store.upsert(secrets_store.Credential(
        exchange_id="bybit", api_key="K", api_secret="S", testnet=True,
    ))
    assert secrets_store.delete("bybit") is True
    assert not secrets_store.has("bybit")
    # idempotent
    assert secrets_store.delete("bybit") is False


def test_atomic_write_no_partial_file(store_env: Path):
    # multiple upserts must result in valid JSON each time
    for i in range(5):
        secrets_store.upsert(secrets_store.Credential(
            exchange_id=f"ex{i}", api_key="K", api_secret="S", testnet=True,
        ))
    ids = secrets_store.list_ids()
    assert ids == [f"ex{i}" for i in range(5)]


def test_mark_verified_updates_timestamp(store_env: Path):
    secrets_store.upsert(secrets_store.Credential(
        exchange_id="bybit", api_key="K", api_secret="S", testnet=True,
    ))
    assert secrets_store.public_view("bybit")["last_verified_at"] is None
    secrets_store.mark_verified("bybit")
    assert secrets_store.public_view("bybit")["last_verified_at"] is not None


def test_corrupt_file_raises_on_read(store_env: Path):
    store_env.parent.mkdir(parents=True, exist_ok=True)
    store_env.write_text("{ not json")
    with pytest.raises(RuntimeError, match="Corrupt"):
        secrets_store.list_ids()
