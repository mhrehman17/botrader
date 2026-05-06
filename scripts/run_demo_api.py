"""Boot the FastAPI app and seed BotState with realistic-looking demo data
so the screens render with content. Run as a subprocess via `python -m`."""
from __future__ import annotations

import math
import os
import random
import time
from pathlib import Path

import pandas as pd
import uvicorn

from botrader.api import secrets_store
from botrader.api.app import create_app
from botrader.api.state import ScanRow, get_state
from botrader.config import BotConfig
from botrader.core.types import Equity, Position, Trade


def seed_demo() -> None:
    s = get_state()
    s.set_mode("paper")
    s.set_running(True)
    s.started_at = int(time.time())

    base_ts = int(time.time() * 1000) - 200 * 60_000
    rng = random.Random(42)

    # Equity curve: 200 points starting at 10_000 with some drift + noise
    eq = 10_000.0
    for i in range(200):
        eq += rng.normalvariate(2.5, 30) + math.sin(i / 25) * 8
        s.push_equity(Equity(ts=base_ts + i * 60_000, equity=eq, cash=eq * 0.9, upnl=eq * 0.1))

    s.set_killswitch(
        tripped=False, reason="",
        peak_equity=max(p.equity for p in s.snapshot_equity()),
        day_start_equity=10_000.0,
    )

    # Demo open positions
    s.set_positions([
        Position(symbol="BTC/USDT:USDT", side="long", qty=0.045,
                 entry_price=68500.0, stop_loss=68080.0, take_profit=69300.0,
                 unrealized_pnl=23.50, leverage=3.0, opened_ts=base_ts + 120_000),
        Position(symbol="ETH/USDT:USDT", side="short", qty=0.50,
                 entry_price=3520.0, stop_loss=3548.0, take_profit=3470.0,
                 unrealized_pnl=-7.25, leverage=3.0, opened_ts=base_ts + 60_000),
    ])

    # Demo trade history
    reasons = ["take_profit_1", "take_profit", "stop_loss", "take_profit_1",
               "take_profit", "stop_loss", "take_profit_1", "take_profit"]
    for i, r in enumerate(reasons):
        side = "long" if i % 2 == 0 else "short"
        entry = 68000 + rng.uniform(-300, 300)
        # winners and losers consistent with the reason
        if r.startswith("take_profit"):
            exit_p = entry + (200 if side == "long" else -200) * (1 if r == "take_profit" else 0.5)
            pnl = 0.04 * (1 if r == "take_profit" else 0.5)
            r_mult = 0.5 if r == "take_profit_1" else 1.5
        else:
            exit_p = entry + (-220 if side == "long" else 220)
            pnl = -0.05
            r_mult = -1.0
        s.push_trade(Trade(
            symbol="BTC/USDT:USDT", side=side,
            entry_ts=base_ts + i * 600_000, exit_ts=base_ts + i * 600_000 + 180_000,
            entry_price=entry, exit_price=exit_p,
            qty=0.05, pnl=pnl, fees=0.002,
            r_multiple=r_mult, reason=r,
        ))

    # Demo scanner state
    s.set_scan({
        "BTC/USDT:USDT": ScanRow(
            symbol="BTC/USDT:USDT", bias="up", state="armed",
            target_price=69200.0, last_close=68750.0,
            ts=base_ts + 199 * 60_000,
        ),
        "ETH/USDT:USDT": ScanRow(
            symbol="ETH/USDT:USDT", bias="down", state="waiting_choch",
            target_price=3470.0, last_close=3520.0,
            ts=base_ts + 199 * 60_000,
        ),
        "SOL/USDT:USDT": ScanRow(
            symbol="SOL/USDT:USDT", bias="none", state="idle",
            target_price=None, last_close=164.5,
            ts=base_ts + 199 * 60_000,
        ),
    })

    # Demo candles for the chart screen — synthesize a 200-bar BTC series
    rows = []
    px = 68500.0
    for i in range(200):
        drift = math.sin(i / 18) * 40 + rng.normalvariate(0, 25)
        o = px
        c = px + drift
        h = max(o, c) + abs(rng.normalvariate(0, 18))
        lo = min(o, c) - abs(rng.normalvariate(0, 18))
        rows.append({"ts": base_ts + i * 5 * 60_000,
                     "open": o, "high": h, "low": lo, "close": c, "volume": 100.0})
        px = c
    df = pd.DataFrame(rows)
    s.set_candles("BTC/USDT:USDT", "5m", df)

    # Demo credentials (encrypted in tmpdir)
    secrets_store.upsert(secrets_store.Credential(
        exchange_id="binanceusdm", api_key="DEMOKEY", api_secret="DEMOSECRET",
        testnet=True, label="demo testnet",
    ))
    secrets_store.mark_verified("binanceusdm")


def main() -> None:
    Path(os.environ.get("BOTRADER_CREDENTIALS_PATH", "/tmp/botrader-demo-creds.enc"))
    cfg = BotConfig()
    app = create_app(cfg)
    seed_demo()
    uvicorn.run(app, host="127.0.0.1", port=8787, log_level="warning")


if __name__ == "__main__":
    main()
