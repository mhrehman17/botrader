"""Pydantic response models. Keep these stable — the mobile app speaks this contract."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Health(BaseModel):
    ok: bool
    mode: Literal["paper", "testnet", "mainnet"] | None
    running: bool
    started_at: int
    version: str


class EquityPoint(BaseModel):
    ts: int
    equity: float
    cash: float
    upnl: float = 0.0


class EquitySnapshot(BaseModel):
    equity: float
    cash: float
    upnl: float
    daily_pnl: float
    peak_equity: float
    initial_equity: float


class PositionOut(BaseModel):
    symbol: str
    side: Literal["long", "short"]
    qty: float
    entry_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    unrealized_pnl: float = 0.0
    leverage: float = 1.0
    opened_ts: int = 0


class TradeOut(BaseModel):
    symbol: str
    side: Literal["long", "short"]
    entry_ts: int
    exit_ts: int
    entry_price: float
    exit_price: float
    qty: float
    pnl: float
    fees: float
    r_multiple: float
    reason: str


class ScanRowOut(BaseModel):
    symbol: str
    bias: Literal["up", "down", "none"]
    state: str
    target_price: float | None
    last_close: float
    ts: int


class KillSwitchOut(BaseModel):
    tripped: bool
    reason: str
    peak_equity: float
    day_start_equity: float


class CandleOut(BaseModel):
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class OrderBlockOut(BaseModel):
    idx: int
    ts: int
    top: float
    bottom: float
    side: Literal["long", "short"]
    mitigated: bool


class FvgOut(BaseModel):
    idx: int
    ts: int
    top: float
    bottom: float
    side: Literal["long", "short"]
    filled: bool


class SweepOut(BaseModel):
    idx: int
    ts: int
    pool_price: float
    is_high: bool
    extreme: float
    close: float


class CandlesResponse(BaseModel):
    symbol: str
    tf: str
    candles: list[CandleOut]
    overlays: dict[str, Any] = Field(default_factory=dict)  # ob, fvg, sweeps lists


class CredentialPublic(BaseModel):
    id: str
    has_key: bool
    label: str = ""
    testnet: bool = True
    created_at: int | None = None
    last_verified_at: int | None = None


class CredentialUpsert(BaseModel):
    api_key: str
    api_secret: str
    testnet: bool = True
    label: str = ""
    options: dict[str, Any] = Field(default_factory=dict)


class CredentialVerify(BaseModel):
    ok: bool
    error: str | None = None
    account_type: str | None = None


class ModeRequest(BaseModel):
    mode: Literal["paper", "testnet", "mainnet"]
    confirm: str | None = None
    exchange_id: str | None = None  # required for testnet/mainnet if multiple creds exist


class BotControlOut(BaseModel):
    ok: bool
    mode: Literal["paper", "testnet", "mainnet"] | None
    running: bool
    message: str = ""


class ConfigOut(BaseModel):
    """Redacted config view. Secrets stripped."""
    mode: str
    symbols: list[str]
    timeframes: dict[str, str]
    strategy: dict[str, Any]
    risk: dict[str, Any]
    exchange: dict[str, Any]  # api_key/secret stripped


class ConfigPatch(BaseModel):
    """Whitelisted config fields the mobile app may patch."""
    risk: dict[str, Any] | None = None
    strategy: dict[str, Any] | None = None
