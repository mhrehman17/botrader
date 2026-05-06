"""Live runner: paper / testnet / mainnet.

The live runner shares strategy, risk, and broker abstractions with the backtest
engine. It polls OHLCV (or subscribes to ws if available), feeds closed bars to
the strategy, and submits brackets via the configured broker.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd

from ..config import BotConfig
from ..data.ohlcv import _make_exchange  # noqa: PLC2701  — internal helper reused
from ..data.resampler import resample_ohlcv
from ..risk.killswitch import KillSwitch
from ..risk.sizing import ContractSpec, size_position
from ..strategy.smc_mtf import SMCStrategy
from ..utils.timeframes import tf_to_ms

log = logging.getLogger(__name__)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _build_broker(cfg: BotConfig, mode: str):
    if mode == "paper":
        from ..execution.paper_broker import PaperBroker
        return PaperBroker(
            initial_cash=cfg.backtest.initial_equity,
            fee_bps=cfg.backtest.fee_bps,
            slippage_bps=cfg.backtest.slippage_bps,
        )
    if mode in ("testnet", "mainnet"):
        from ..execution.ccxt_broker import CcxtBroker
        return CcxtBroker(cfg.exchange, mode=mode)
    raise ValueError(f"Unknown live mode: {mode}")


def _fetch_recent(ex, symbol: str, tf: str, limit: int = 500) -> pd.DataFrame:
    rows = ex.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = df["ts"].astype("int64")
    return df


def _drop_unclosed(df: pd.DataFrame, tf: str, now_ms: int) -> pd.DataFrame:
    step = tf_to_ms(tf)
    if df.empty:
        return df
    last_open = int(df["ts"].iloc[-1])
    if now_ms < last_open + step:
        df = df.iloc[:-1]
    return df.reset_index(drop=True)


def run_live(
    cfg: BotConfig,
    run_dir: Path,
    mode: str,
    force_signal: str | None = None,
) -> None:
    log.warning("Starting live runner mode=%s. Symbols=%s", mode, cfg.symbols)
    if mode in ("testnet", "mainnet") and not (cfg.exchange.api_key and cfg.exchange.api_secret):
        log.error("API key/secret missing in config or env. Aborting.")
        return

    ex = _make_exchange(cfg.exchange.id)
    if cfg.exchange.testnet and hasattr(ex, "set_sandbox_mode"):
        ex.set_sandbox_mode(True)

    broker = _build_broker(cfg, mode)
    strategy = SMCStrategy(cfg.strategy, cfg.risk)
    ks = KillSwitch(cfg.risk.daily_loss_kill_pct, cfg.risk.max_drawdown_kill_pct)
    spec = ContractSpec()

    ltf_step_ms = tf_to_ms(cfg.timeframes.ltf)
    log.info("Polling OHLCV every %d ms.", min(ltf_step_ms, 5000))

    last_seen_ts: dict[str, int] = {}

    try:
        while True:
            now = _now_ms()
            for sym in cfg.symbols:
                ltf = _fetch_recent(ex, sym, cfg.timeframes.ltf, limit=500)
                ltf = _drop_unclosed(ltf, cfg.timeframes.ltf, now)
                if ltf.empty:
                    continue
                last_close_ts = int(ltf["ts"].iloc[-1])
                if last_seen_ts.get(sym) == last_close_ts:
                    continue
                last_seen_ts[sym] = last_close_ts

                # Feed bar to broker (paper broker uses for fills; live broker is no-op)
                row = ltf.iloc[-1]
                broker.on_bar(sym, last_close_ts, float(row["open"]), float(row["high"]),
                              float(row["low"]), float(row["close"]))

                eq = broker.equity()
                tripped, reason = ks.update(last_close_ts, eq)
                if tripped:
                    log.error("Kill switch tripped: %s. Cancelling all orders.", reason)
                    broker.cancel_all()
                    continue

                htf = resample_ohlcv(ltf, cfg.timeframes.ltf, cfg.timeframes.htf)
                if len(htf) < 30:
                    continue

                signals = strategy.on_bar(sym, ltf, htf)
                if force_signal and not signals:
                    from ..core.types import Signal
                    px = float(ltf["close"].iloc[-1])
                    if force_signal == "long":
                        signals = [Signal(side="long", entry=px, stop_loss=px * 0.995,
                                          take_profit_1=px * 1.005, take_profit_2=None,
                                          reason="force_signal", htf_bias="up", ts=last_close_ts)]
                    else:
                        signals = [Signal(side="short", entry=px, stop_loss=px * 1.005,
                                          take_profit_1=px * 0.995, take_profit_2=None,
                                          reason="force_signal", htf_bias="down", ts=last_close_ts)]
                    force_signal = None  # one-shot

                if any(p.symbol == sym for p in broker.positions()):
                    continue

                for sig in signals:
                    qty = size_position(
                        equity=eq, risk_pct=cfg.risk.risk_pct_per_trade,
                        entry=sig.entry, stop_loss=sig.stop_loss,
                        spec=spec, max_leverage=cfg.risk.max_leverage,
                    )
                    if qty <= 0:
                        continue
                    if len(broker.positions()) >= cfg.risk.max_concurrent_positions:
                        break
                    cid = f"{sym}-{last_close_ts}"
                    broker.submit_bracket(
                        symbol=sym, side=sig.side, qty=qty,
                        entry_price=sig.entry, stop_loss=sig.stop_loss,
                        take_profit=sig.take_profit_1, client_id=cid,
                    )
                    log.info("LIVE bracket %s qty=%.4f entry=%.2f sl=%.2f tp=%.2f",
                             sig.side, qty, sig.entry, sig.stop_loss, sig.take_profit_1)

            time.sleep(min(ltf_step_ms / 1000, 5))
    except KeyboardInterrupt:
        log.info("Stopping live runner. Cancelling open orders.")
        broker.cancel_all()


def run_scan(cfg: BotConfig, once: bool = True) -> None:
    """Print current SMC state for each symbol; never places an order."""
    ex = _make_exchange(cfg.exchange.id)
    if cfg.exchange.testnet and hasattr(ex, "set_sandbox_mode"):
        ex.set_sandbox_mode(True)
    strategy = SMCStrategy(cfg.strategy, cfg.risk)
    while True:
        now = _now_ms()
        for sym in cfg.symbols:
            ltf = _fetch_recent(ex, sym, cfg.timeframes.ltf, limit=500)
            ltf = _drop_unclosed(ltf, cfg.timeframes.ltf, now)
            if ltf.empty:
                continue
            htf = resample_ohlcv(ltf, cfg.timeframes.ltf, cfg.timeframes.htf)
            sigs = strategy.on_bar(sym, ltf, htf)
            ctx = strategy._ctx_for(sym)  # noqa: SLF001
            log.info(
                "%s bias=%s state=%s target=%s last_close=%.4f signals=%d",
                sym, ctx.htf_bias, ctx.state,
                f"{ctx.htf_target_price:.4f}" if ctx.htf_target_price else "none",
                float(ltf["close"].iloc[-1]),
                len(sigs),
            )
        if once:
            break
        time.sleep(30)
