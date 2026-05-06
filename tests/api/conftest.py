"""Shared API test fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from botrader.api import secrets_store
from botrader.api.app import create_app
from botrader.api.runtime import reset_runtime
from botrader.api.state import reset_state
from botrader.config import BotConfig


@pytest.fixture
def env(tmp_path: Path, monkeypatch):
    """Set required env vars and a temporary credentials path."""
    monkeypatch.setenv("BOTRADER_API_TOKEN", "test-token")
    monkeypatch.setenv("BOTRADER_MASTER_KEY", "test-master")
    monkeypatch.setenv("BOTRADER_CREDENTIALS_PATH", str(tmp_path / "creds.enc"))
    monkeypatch.delenv("BOTRADER_ALLOW_MAINNET", raising=False)
    yield
    reset_state()
    reset_runtime()


@pytest.fixture
def cfg() -> BotConfig:
    return BotConfig()


@pytest.fixture
def client(env, cfg) -> TestClient:  # noqa: ARG001 — env is for setup
    return TestClient(create_app(cfg))


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def saved_credential(env):  # noqa: ARG001 — env is for setup
    secrets_store.upsert(secrets_store.Credential(
        exchange_id="binanceusdm",
        api_key="K", api_secret="S",
        testnet=True, label="t",
    ))
