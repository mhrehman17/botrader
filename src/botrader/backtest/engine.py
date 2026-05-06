"""Event-driven backtest engine.

Algorithm per LTF bar:
  1. Update broker with this bar's OHLC (fills, SL/TP triggers, mark price).
  2. Update HTF view (synthesized from LTF up to *current* time — no lookahead).
  3. Sample equity into the equity curve.
  4. Update kill-switch; if tripped, cancel all and stop placing new trades.
  5. Call strategy.on_bar with closed-bar history up to and including this bar.
  6. For each new signal: size position, submit bracket order.
  7. Manage TTL on resting limit orders (cancel after entry_ttl_bars).

Slippage & fees are applied inside the sim_broker.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ..config import BotConfig
from ..core.types import (
    BacktestResult,
    Equity,
)
from ..data.ohlcv import load_range
from ..data.resampler import resample_ohlcv
from ..risk.killswitch import KillSwitch
from ..risk.sizing import ContractSpec, dd_risk_factor, size_position
from ..strategy.smc_mtf import SMCStrategy
from ..utils.timeframes import tf_to_ms
from .metrics import all_metrics
from .report import write_report

log = logging.getLogger(__name__)


def _date_to_ms(d) -> int:
    return int(pd.Timestamp(d).tz_localize("UTC").value // 1_000_000)


def run_backtest(cfg: BotConfig, run_dir: Path) -> BacktestResult:
    from ..execution.sim_broker import SimBroker

    if not cfg.symbols:
        raise ValueError("At least one symbol must be configured")

    start_ms = _date_to_ms(cfg.backtest.start)
    end_ms = _date_to_ms(cfg.backtest.end)

    # Load LTF data per symbol (require cached parquet)
    data: dict[str, pd.DataFrame] = {}
    for sym in cfg.symbols:
        df = load_range(
            cfg.data.cache_dir, cfg.exchange.id, sym, cfg.timeframes.ltf,
            start_ms=start_ms, end_ms=end_ms,
        )
        if df.empty:
            raise FileNotFoundError(
                f"No cached LTF data for {sym} {cfg.timeframes.ltf}. "
                f"Run: botrader fetch-data --exchange {cfg.exchange.id} "
                f"--symbol \"{sym}\" --tf {cfg.timeframes.ltf} --since {cfg.backtest.start}"
            )
        data[sym] = df

    broker = SimBroker(
        initial_cash=cfg.backtest.initial_equity,
        fee_bps=cfg.backtest.fee_bps,
        slippage_bps=cfg.backtest.slippage_bps,
    )
    strategy = SMCStrategy(cfg.strategy, cfg.risk)
    ks = KillSwitch(cfg.risk.daily_loss_kill_pct, cfg.risk.max_drawdown_kill_pct)
    spec = ContractSpec()  # default; could be loaded from exchange via ccxt later

    equity_curve: list[Equity] = []
    ltf_step_ms = tf_to_ms(cfg.timeframes.ltf)

    # Find the global timeline from the union of LTF timestamps (sorted).
    all_ts = sorted({int(t) for df in data.values() for t in df["ts"]})
    log.info("Backtest %d bars across %d symbols", len(all_ts), len(cfg.symbols))

    # Per-symbol histories for fast slicing
    sym_idx: dict[str, int] = dict.fromkeys(data.keys(), 0)
    htf_lookback = cfg.strategy.htf_lookback_bars
    ltf_lookback = cfg.strategy.ltf_lookback_bars

    bar_count = 0
    for ts in all_ts:
        for sym, df in data.items():
            i = sym_idx[sym]
            if i >= len(df) or int(df["ts"].iloc[i]) != ts:
                continue
            row = df.iloc[i]
            broker.on_bar(
                sym, ts,
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
            )
            sym_idx[sym] = i + 1

        equity = broker.equity()
        equity_curve.append(Equity(ts=ts, equity=equity, cash=broker.balance()))

        tripped, reason = ks.update(ts, equity)
        if tripped:
            for sym in cfg.symbols:
                broker.cancel_all(sym)
            # don't break — still need to mark-to-market remaining positions until they close
            continue

        # Periodic strategy call (every LTF bar) per symbol.
        for sym, df in data.items():
            # Slice closed history through this ts.
            i = sym_idx[sym]
            if i == 0:
                continue
            ltf_view = df.iloc[max(0, i - ltf_lookback):i].reset_index(drop=True)
            if ltf_view.empty or int(ltf_view["ts"].iloc[-1]) != ts:
                continue
            htf_view = resample_ohlcv(ltf_view, cfg.timeframes.ltf, cfg.timeframes.htf)
            if len(htf_view) < 30:
                continue
            htf_view = htf_view.tail(htf_lookback).reset_index(drop=True)

            signals = strategy.on_bar(sym, ltf_view, htf_view)
            if not signals:
                # TTL: cancel limits older than entry_ttl_bars
                _expire_limits(broker, sym, ts, cfg, ltf_step_ms)
                continue

            # only one position per symbol at a time
            if any(p.symbol == sym for p in broker.positions()):
                continue

            for sig in signals:
                # Drawdown-aware sizing: shrink risk after a losing streak.
                dd_factor = dd_risk_factor(
                    broker.trades() if hasattr(broker, "trades") else [],
                    cfg.risk.dd_loss_streak,
                    cfg.risk.dd_risk_multiplier,
                )
                qty = size_position(
                    equity=broker.equity(),
                    risk_pct=cfg.risk.risk_pct_per_trade * dd_factor,
                    entry=sig.entry,
                    stop_loss=sig.stop_loss,
                    spec=spec,
                    max_leverage=cfg.risk.max_leverage,
                )
                if qty <= 0:
                    continue
                if len(broker.positions()) >= cfg.risk.max_concurrent_positions:
                    break
                client_id = f"{sym}-{ts}"
                broker.submit_smc_bracket(
                    symbol=sym, side=sig.side, qty=qty,
                    entry_price=sig.entry, stop_loss=sig.stop_loss,
                    take_profit_1=sig.take_profit_1,
                    take_profit_2=sig.take_profit_2,
                    partial_pct=cfg.strategy.partial_tp_pct,
                    client_id=client_id,
                )
                log.info("Placed SMC bracket %s qty=%.4f entry=%.2f sl=%.2f tp1=%.2f tp2=%s",
                         sig.side, qty, sig.entry, sig.stop_loss, sig.take_profit_1,
                         f"{sig.take_profit_2:.2f}" if sig.take_profit_2 else "none")

        # Exit-management: ATR trailing past 1R for any open positions.
        if cfg.risk.trail_atr_mult > 0:
            _manage_trailing_stops(broker, data, sym_idx, cfg)

        bar_count += 1
        if bar_count % 5000 == 0:
            log.info("[%d] %s eq=%.2f", bar_count,
                     pd.to_datetime(ts, unit="ms"), equity)

    # Close any remaining positions at the last close
    for sym in list(p.symbol for p in broker.positions()):
        broker.close_position(sym)

    metrics = all_metrics(equity_curve, broker.trades())
    result = BacktestResult(
        equity_curve=equity_curve,
        trades=broker.trades(),
        metrics=metrics,
    )
    write_report(result, run_dir)
    summary = {k: round(v, 4) if isinstance(v, float) else v for k, v in metrics.items()}
    log.info("METRICS: %s", summary)
    return result


def _atr_from(df: pd.DataFrame, period: int) -> float:
    if len(df) < period + 1:
        return 0.0
    h = df["high"].to_numpy()
    low = df["low"].to_numpy()
    c = df["close"].to_numpy()
    import numpy as np
    prev_c = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum.reduce([h - low, np.abs(h - prev_c), np.abs(low - prev_c)])
    return float(tr[-period:].mean())


def _manage_trailing_stops(broker, data: dict[str, pd.DataFrame], sym_idx: dict[str, int],
                           cfg: BotConfig) -> None:
    """For any open SMC position whose MFE has reached 1R, trail the SL by trail_atr_mult * ATR.
    Only ratchets in the favorable direction."""
    for pos in broker.positions():
        meta = broker.position_meta(pos.symbol) if hasattr(broker, "position_meta") else None
        if not meta:
            continue
        entry = meta["entry_price"]
        original_sl = meta["original_sl"]
        mfe = meta["mfe_price"]
        cur_sl = meta["current_sl"]
        side = meta["side"]
        risk = abs(entry - original_sl)
        if risk <= 0:
            continue
        # Past 1R?
        if side == "long" and (mfe - entry) < risk:
            continue
        if side == "short" and (entry - mfe) < risk:
            continue
        # Compute ATR from latest LTF window
        df = data.get(pos.symbol)
        if df is None:
            continue
        i = sym_idx.get(pos.symbol, 0)
        window = df.iloc[max(0, i - 200):i]
        atr = _atr_from(window, cfg.risk.sl_atr_period)
        if atr <= 0:
            continue
        last_close = float(window["close"].iloc[-1]) if not window.empty else entry
        new_sl = (last_close - cfg.risk.trail_atr_mult * atr) if side == "long" else (
            last_close + cfg.risk.trail_atr_mult * atr
        )
        # Ratchet only in favorable direction
        if cur_sl is not None:
            if side == "long" and new_sl <= cur_sl:
                continue
            if side == "short" and new_sl >= cur_sl:
                continue
        # Don't trail through current price (would close immediately)
        if side == "long" and new_sl >= last_close:
            continue
        if side == "short" and new_sl <= last_close:
            continue
        broker.modify_stop(pos.symbol, new_sl)


def _expire_limits(broker, symbol: str, ts: int, cfg: BotConfig, ltf_step_ms: int) -> None:
    """Cancel resting limits older than entry_ttl_bars*ltf_step_ms."""
    ttl_ms = cfg.strategy.entry_ttl_bars * ltf_step_ms
    for o in broker.open_orders(symbol):
        # only entry limits
        if o.type.value != "limit":
            continue
        # heuristic: if no fill and order has been resting >= TTL, cancel.
        # client_id encodes ts: "<sym>-<ts>"
        if not o.client_id or "-" not in o.client_id:
            continue
        try:
            placed_ts = int(o.client_id.rsplit("-", 1)[1])
        except ValueError:
            continue
        if ts - placed_ts >= ttl_ms:
            broker.cancel_order(o.id)
            # also cancel bracket children (SL + TP attached to this entry)
            for child_id in broker._brackets.get(o.id, []):  # noqa: SLF001
                broker.cancel_order(child_id)
