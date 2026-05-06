"""/bot/mode gate tests: paper/testnet/mainnet flow."""
from __future__ import annotations

from unittest.mock import patch


def test_paper_mode_works_without_credentials(client, auth):
    r = client.post("/bot/mode", json={"mode": "paper"}, headers=auth)
    assert r.status_code == 200
    j = r.json()
    assert j["mode"] == "paper"


def test_testnet_requires_saved_credential(client, auth):
    r = client.post("/bot/mode", json={"mode": "testnet"}, headers=auth)
    assert r.status_code == 400
    assert "credentials" in r.json()["detail"].lower()


def test_testnet_with_saved_credential_succeeds(client, auth, saved_credential):  # noqa: ARG001
    # Patch CcxtBroker at the import site `_build_broker` uses
    # (`from ..execution.ccxt_broker import CcxtBroker`).
    with patch("botrader.execution.ccxt_broker.CcxtBroker") as mock_broker:
        mock_broker.return_value.cancel_all.return_value = None
        r = client.post("/bot/mode", json={"mode": "testnet"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["mode"] == "testnet"


def test_mainnet_rejected_without_env_flag(client, auth, saved_credential):  # noqa: ARG001
    # Even with confirm + credentials, missing env var -> 403
    r = client.post(
        "/bot/mode",
        json={"mode": "mainnet", "confirm": "MAINNET"},
        headers=auth,
    )
    assert r.status_code == 403
    assert "BOTRADER_ALLOW_MAINNET" in r.json()["detail"]


def test_mainnet_rejected_without_confirm_phrase(client, auth, monkeypatch, saved_credential):  # noqa: ARG001
    monkeypatch.setenv("BOTRADER_ALLOW_MAINNET", "1")
    r = client.post("/bot/mode", json={"mode": "mainnet"}, headers=auth)
    assert r.status_code == 403
    assert "MAINNET" in r.json()["detail"]


def test_mainnet_rejected_when_credential_is_testnet_only(
    client, auth, monkeypatch, saved_credential,  # noqa: ARG001
):
    """The fixture stores a testnet credential. Even with all gates open,
    using it for mainnet must fail with a clear error."""
    monkeypatch.setenv("BOTRADER_ALLOW_MAINNET", "1")
    with patch("botrader.execution.ccxt_broker.CcxtBroker"):
        r = client.post(
            "/bot/mode",
            json={"mode": "mainnet", "confirm": "MAINNET"},
            headers=auth,
        )
    assert r.status_code == 400
    assert "testnet-only" in r.json()["detail"]


def test_bot_start_stop(client, auth):
    # default to paper
    r = client.post("/bot/mode", json={"mode": "paper"}, headers=auth)
    assert r.status_code == 200
    # start (the loop tries to fetch ccxt; it will warn but not crash since
    # the bot loop sleeps on errors). Stop quickly to avoid background work.
    with patch("botrader.api.runtime._make_exchange") as mk:
        mk.return_value.fetch_ohlcv.return_value = []
        r = client.post("/bot/start", headers=auth)
        assert r.status_code == 200
        assert r.json()["running"] is True
        r = client.post("/bot/stop", headers=auth)
        assert r.status_code == 200
        assert r.json()["running"] is False
