"""Endpoint shape, auth, and config-redaction tests."""
from __future__ import annotations


def test_healthz_requires_auth(client):
    r = client.get("/healthz")
    assert r.status_code == 401
    assert "Bearer" in r.json()["detail"]


def test_healthz_ok(client, auth):
    r = client.get("/healthz", headers=auth)
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["mode"] is None
    assert j["running"] is False


def test_config_redacts_secrets(client, auth):
    r = client.get("/config", headers=auth)
    assert r.status_code == 200
    j = r.json()
    assert "exchange" in j
    # Even though default config has empty key/secret, the field should never
    # contain the literal ones — and no plaintext if set.
    assert j["exchange"]["api_key"] in ("", "••••••••")
    assert j["exchange"]["api_secret"] in ("", "••••••••")


def test_config_patch_whitelist(client, auth):
    # legal field
    r = client.put("/config", json={"risk": {"risk_pct_per_trade": 0.001}}, headers=auth)
    assert r.status_code == 200
    assert r.json()["risk"]["risk_pct_per_trade"] == 0.001
    # illegal field
    r = client.put("/config", json={"risk": {"hacker_mode": True}}, headers=auth)
    assert r.status_code == 400


def test_credentials_list_empty(client, auth):
    r = client.get("/credentials", headers=auth)
    assert r.status_code == 200
    assert r.json() == []


def test_credentials_upsert_then_list(client, auth):
    r = client.put(
        "/credentials/binanceusdm",
        json={"api_key": "K", "api_secret": "S", "testnet": True, "label": "t"},
        headers=auth,
    )
    assert r.status_code == 200
    j = r.json()
    assert j["id"] == "binanceusdm"
    assert j["has_key"] is True
    # No plaintext fields leaked
    assert "api_key" not in j
    assert "api_secret" not in j

    r = client.get("/credentials", headers=auth)
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["id"] == "binanceusdm"


def test_credentials_delete(client, auth, saved_credential):  # noqa: ARG001
    r = client.delete("/credentials/binanceusdm", headers=auth)
    assert r.status_code == 200
    r = client.get("/credentials", headers=auth)
    assert r.json() == []


def test_killswitch_default(client, auth):
    r = client.get("/killswitch", headers=auth)
    assert r.status_code == 200
    assert r.json()["tripped"] is False


def test_server_info_advertises_mainnet_capability(client, auth):
    r = client.get("/server-info", headers=auth)
    assert r.status_code == 200
    j = r.json()
    assert "allow_mainnet" in j
    assert j["allow_mainnet"] is False  # env var not set in fixture


def test_equity_empty_curve(client, auth):
    r = client.get("/equity", headers=auth)
    assert r.status_code == 200
    j = r.json()
    assert j["equity"] == 0.0
    r = client.get("/equity-curve", headers=auth)
    assert r.status_code == 200
    assert r.json() == []


def test_positions_and_trades_empty(client, auth):
    assert client.get("/positions", headers=auth).json() == []
    assert client.get("/trades", headers=auth).json() == []


def test_scan_empty(client, auth):
    assert client.get("/scan", headers=auth).json() == []


def test_candles_404_when_missing(client, auth):
    r = client.get("/candles?symbol=BTC%2FUSDT%3AUSDT&tf=5m", headers=auth)
    assert r.status_code == 404
