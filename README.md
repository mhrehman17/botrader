# botrader

Smart Money Concepts (SMC) day-trading bot for crypto futures markets — multi-exchange via [ccxt](https://github.com/ccxt/ccxt).

## Risk disclaimer

> **No trading bot is guaranteed profitable.** This codebase mechanizes a discretionary framework (Smart Money Concepts), and parameter choices materially change results. Crypto futures involve leverage and liquidation risk. **Backtest, walk-forward, paper-trade, and testnet** before risking real capital. The authors accept no responsibility for losses. Tax/regulatory compliance is your responsibility.

## Features

- **Smart Money Concepts (SMC):**
  - Market structure: swings, BOS, CHoCH (HH/HL/LH/LL)
  - Order Blocks (bullish & bearish, with mitigation tracking)
  - Fair Value Gaps (3-candle imbalances, fill tracking)
  - Liquidity pools (equal highs/lows) and sweeps (stop hunts)
- **Multi-timeframe:** HTF bias (1h/4h) drives LTF entries (5m/15m).
- **Risk management:** % risk per trade, daily-loss kill-switch, max-drawdown kill-switch, leverage cap, funding-window blackout.
- **Modes:** `backtest` → `paper` → `live` (testnet) → `live` (mainnet, gated).
- **Multi-exchange via ccxt:** Binance USDT-M, Bybit USDT perps, OKX, Bitget, etc.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 1. Fetch some historical data (example: BTC/USDT perp on Binance)
botrader fetch-data --exchange binanceusdm --symbol "BTC/USDT:USDT" --tf 5m --since 2024-06-01
botrader fetch-data --exchange binanceusdm --symbol "BTC/USDT:USDT" --tf 1h --since 2024-06-01

# 2. Backtest
botrader backtest --config configs/backtest.yaml

# 3. Inspect output
ls runs/

# 4. Paper trade against live data
botrader paper --config configs/paper.yaml

# 5. Live trade on testnet (after keys in .env)
botrader live --config configs/testnet.yaml
```

## Strategy in one paragraph

Compute the higher-timeframe market structure to set a directional bias (bullish if last event was BOS up or CHoCH up; mirror for bearish). On the lower timeframe, wait for a liquidity sweep aligned with HTF bias (longs sweep an LTF low pool), then for an LTF CHoCH confirming the reversal. Place a limit order at the LTF order block that produced the CHoCH (entry at OB midpoint / OTE). SL goes beyond the sweep extreme by `sl_atr_mult * ATR(14)`. TP1 = nearest opposing LTF FVG (partial 50%); TP2 = HTF liquidity target. After TP1, move SL to breakeven. Skip entries during funding-rate blackout windows. Respect daily-loss and max-drawdown kill-switches.

## Project layout

See `/root/.claude/plans/understand-this-code-and-parsed-blum.md` for the full design. Source under `src/botrader/`, tests under `tests/`, configs under `configs/`.

## Pre-mainnet checklist

1. **Backtest** ≥ 6 months on the symbols you intend to trade.
2. **Walk-forward**: train on first half, evaluate on second half. Don't curve-fit.
3. **Paper trade** ≥ 2 weeks against live data.
4. **Testnet** ≥ 2 weeks with the live broker code path.
5. **Mainnet at 0.1% risk** before scaling up. Gate with `--i-understand-the-risks`.

## Honest caveats

- **Lookahead bias:** swings are confirmed only after `right` bars elapse — never act on unconfirmed swings.
- **Repainting:** OBs/FVGs redefine as new structure forms. The engine persists as-of-bar state.
- **Slippage & fees:** modeled in `sim_broker` (defaults: 4 bps fee, 2 bps slippage); tune to your exchange tier.
- **Funding & liquidations:** funding cost is included on holds; high leverage near sweeps can liquidate before SL fires — the code uses exchange-side reduce-only SL where supported.
- **Survivorship bias:** backtesting only on BTC/ETH ignores delistings.

## License

MIT
