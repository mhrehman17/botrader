# Expected-value upgrades: minimum R:R, drawdown-aware sizing

This page explains the EV-focused changes added to the SMC strategy and how to
evaluate them honestly.

## Why win-rate is the wrong target

A trading strategy's profitability is governed by *expectancy* — the average
P&L per trade — not by win-rate alone. The math:

```
expectancy = win_rate * avg_win  -  loss_rate * avg_loss  -  fees_per_trade
```

You can engineer a 90%+ win-rate by tightening TP1 and widening SL — every
trade scrapes a small win, and the rare loser destroys an outsized chunk of
equity. The win-rate column looks great. The equity curve goes down. **High
win-rate is a sign of trader discipline mostly when paired with a positive
profit factor**; on its own it is uninformative.

The variant comparison script reports columns in this priority order:

1. `expectancy`  — actual edge per trade
2. `profit_factor` — gross_win / gross_loss
3. `total_return_pct`, `max_drawdown`
4. `sharpe`, `sortino`
5. `win_rate` — *last*, with a reminder that it doesn't predict P&L
6. R-distribution (`avgR`, `+R`, `-R`, `Rsd`) — sanity check on tails

Sample sizes under 30 are noise. The script tells you so.

## What was added

### 1. `strategy.min_rr_to_tp1` (default 1.0)

Before opening a position, the engine computes
`R:R = |TP1 - entry| / |entry - SL|`. If it's below `min_rr_to_tp1`, the
trade is rejected. The default of 1.0 means TP1 must be at least one SL
distance away — the floor below which fees and slippage typically eat any
edge regardless of win-rate.

### 2. `strategy.max_sl_atr_mult` (default 4.0)

Caps SL distance to N×ATR(`sl_atr_period`). When a sweep is wide, the SL
beyond it can become huge relative to ATR, ballooning risk and capping R:R.
This filter rejects those setups.

### 3. `risk.dd_loss_streak` + `risk.dd_risk_multiplier` (default 3, 1.0)

Drawdown-aware sizing. After `dd_loss_streak` consecutive losing trades,
multiply per-trade risk by `dd_risk_multiplier` until a winning trade
resets the streak. `multiplier=1.0` disables the feature. A common setting
is `multiplier=0.5` (halve risk after 3 losses) — preserves capital during
adverse regimes without forcing you to stop trading entirely.

### 4. `scripts/compare_variants.py`

Runs N config variants on the same cached OHLCV and prints a side-by-side
metrics table.  Provided so you can A/B the gates yourself on real data.

```text
            name      n       exp$       PF      ret%      MDD       sh   ...
 legacy_no_gates      1    -94.35    0.00    -1.74%    1.7%   -4.19  ...
      min_rr_1.0      0     +0.00    0.00    +0.00%    0.0%    0.00  ...
      ...
```

## Honest caveats

- **Synthetic data is not validation.** The metrics produced by running this
  comparison against random-walk synthetic OHLCV (which is all I can use in
  a sandboxed environment) tell you nothing about live performance. Use it
  on real cached candles for any meaningful comparison.
- **Walk-forward is mandatory.** Tuning these gates against a single
  historical window guarantees you'll curve-fit. Split your cache into
  train and test, choose parameters on train, report only on test.
- **The gates are theoretically grounded, not data-mined.** Both filters
  reject negative-EV setups by math (R:R < 1 is bad fundamentally,
  regardless of which dataset you test it on). The DD-aware sizing is a
  capital-preservation rule, not a signal optimization.
- **None of this is guaranteed to make the bot profitable.** SMC is a
  discretionary framework. Mechanizing it forces choices that materially
  change results, and parameter sensitivity is high. Backtest, walk-forward,
  paper, testnet — in that order — before mainnet.
