"""Bot runtime: orchestrates the trading loop in a background thread.

The runtime owns:
- A `Broker` instance (PaperBroker or CcxtBroker).
- A `BotConfig`.
- A background thread running a tight loop that pulls candles, calls the
  strategy, and pushes state into `BotState`.

Mode-toggle is handled here: `switch_mode(target, exchange_id)` stops the
loop, swaps the broker, and (if previously running) restarts it.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Literal

from ..config import BotConfig, ExchangeConfig
from ..core.types import Equity
from ..data.ohlcv import _make_exchange  # noqa: PLC2701  — internal helper reused
from ..data.resampler import resample_ohlcv
from ..risk.killswitch import KillSwitch
from ..risk.sizing import ContractSpec, size_position
from ..strategy.smc_mtf import SMCStrategy
from ..utils.timeframes import tf_to_ms
from . import secrets_store
from .state import BotState, ScanRow, get_state

log = logging.getLogger(__name__)

Mode = Literal["paper", "testnet", "mainnet"]


def _now_ms() -> int:
    return int(time.time() * 1000)


def _build_broker(cfg: BotConfig, mode: Mode, exchange_id: str | None):
    if mode == "paper":
        from ..execution.paper_broker import PaperBroker
        return PaperBroker(
            initial_cash=cfg.backtest.initial_equity,
            fee_bps=cfg.backtest.fee_bps,
            slippage_bps=cfg.backtest.slippage_bps,
        )
    # testnet/mainnet: load credentials, build CcxtBroker
    from ..execution.ccxt_broker import CcxtBroker
    ex_id = exchange_id or cfg.exchange.id
    cred = secrets_store.load_for(ex_id)
    if cred is None:
        raise ValueError(
            f"No credentials configured for {ex_id}. "
            "Add via the mobile Settings → API Keys, or `botrader credentials add`."
        )
    if mode == "mainnet" and cred.testnet:
        raise ValueError(
            f"Credential for {ex_id} is testnet-only; cannot use for mainnet mode."
        )
    ex_cfg = ExchangeConfig(
        id=ex_id, testnet=(mode == "testnet"),
        api_key=cred.api_key, api_secret=cred.api_secret,
        options=cred.options,
    )
    return CcxtBroker(ex_cfg, mode="mainnet" if mode == "mainnet" else "testnet")


class BotRuntime:
    def __init__(self, cfg: BotConfig):
        self.cfg = cfg
        self.state: BotState = get_state()
        self.broker = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._mode_lock = threading.RLock()
        self._strategy = SMCStrategy(cfg.strategy, cfg.risk)
        self._kill = KillSwitch(cfg.risk.daily_loss_kill_pct, cfg.risk.max_drawdown_kill_pct)
        self._spec = ContractSpec()

    # ---- public API ----
    def switch_mode(self, mode: Mode, exchange_id: str | None = None,
                    confirm: str | None = None) -> None:
        """Stop the loop, swap the broker, optionally restart. Raises on validation errors."""
        with self._mode_lock:
            self._validate_mode(mode, exchange_id, confirm)
            was_running = self.state.running
            self._stop_loop()
            self.broker = _build_broker(self.cfg, mode, exchange_id)
            self.state.set_mode(mode)
            log.info("Mode switched to %s (exchange=%s)", mode, exchange_id or self.cfg.exchange.id)
            if was_running:
                self._start_loop()

    def start(self) -> None:
        with self._mode_lock:
            if self.state.mode is None:
                # default to paper if not yet set
                self.broker = _build_broker(self.cfg, "paper", None)
                self.state.set_mode("paper")
            self._start_loop()

    def stop(self, reason: str = "user") -> None:
        with self._mode_lock:
            self._stop_loop(reason=reason)

    # ---- internal ----
    def _validate_mode(self, mode: Mode, exchange_id: str | None, confirm: str | None) -> None:
        if mode == "mainnet":
            if os.environ.get("BOTRADER_ALLOW_MAINNET", "") != "1":
                raise PermissionError(
                    "BOTRADER_ALLOW_MAINNET not set. Restart the server with this env var set "
                    "to '1' to enable mainnet."
                )
            if confirm != "MAINNET":
                raise PermissionError(
                    "Mainnet requires confirm='MAINNET' in the request body."
                )
        if mode in ("testnet", "mainnet"):
            ex_id = exchange_id or self.cfg.exchange.id
            if not secrets_store.has(ex_id):
                raise ValueError(f"No credentials configured for {ex_id}.")

    def _start_loop(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="botrader-loop")
        self._thread.start()
        self.state.set_running(True)

    def _stop_loop(self, reason: str = "") -> None:
        if self._thread is None:
            self.state.set_running(False, reason=reason)
            return
        self._stop_event.set()
        if self.broker is not None:
            try:
                self.broker.cancel_all()
            except Exception as e:  # noqa: BLE001
                log.warning("cancel_all on stop failed: %s", e)
        self._thread.join(timeout=10)
        self._thread = None
        self.state.set_running(False, reason=reason)

    def _run(self) -> None:
        cfg = self.cfg
        ltf_step_ms = tf_to_ms(cfg.timeframes.ltf)
        last_seen_ts: dict[str, int] = {}

        # Use ccxt public client for OHLCV fetch (works for paper too).
        ex = _make_exchange(cfg.exchange.id)
        if cfg.exchange.testnet and hasattr(ex, "set_sandbox_mode"):
            ex.set_sandbox_mode(True)

        log.info("Bot loop started")
        while not self._stop_event.is_set():
            now = _now_ms()
            scan_rows: dict[str, ScanRow] = {}
            for sym in cfg.symbols:
                try:
                    rows = ex.fetch_ohlcv(sym, timeframe=cfg.timeframes.ltf, limit=500)
                except Exception as e:  # noqa: BLE001
                    log.warning("fetch_ohlcv failed for %s: %s", sym, e)
                    continue
                if not rows:
                    continue
                import pandas as pd
                ltf = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
                ltf["ts"] = ltf["ts"].astype("int64")
                # drop unclosed bar
                if not ltf.empty and now < int(ltf["ts"].iloc[-1]) + ltf_step_ms:
                    ltf = ltf.iloc[:-1].reset_index(drop=True)
                if ltf.empty:
                    continue
                last_close_ts = int(ltf["ts"].iloc[-1])
                if last_seen_ts.get(sym) == last_close_ts:
                    continue
                last_seen_ts[sym] = last_close_ts

                row = ltf.iloc[-1]
                self.broker.on_bar(sym, last_close_ts, float(row["open"]), float(row["high"]),
                                   float(row["low"]), float(row["close"]))
                self.state.set_candles(sym, cfg.timeframes.ltf, ltf)

                eq_value = self.broker.equity()
                self.state.push_equity(Equity(
                    ts=last_close_ts, equity=eq_value, cash=self.broker.balance(),
                ))
                tripped, reason = self._kill.update(last_close_ts, eq_value)
                self.state.set_killswitch(
                    tripped=tripped, reason=reason,
                    peak_equity=self._kill._peak_equity,  # noqa: SLF001
                    day_start_equity=self._kill._day_start_equity or 0.0,  # noqa: SLF001
                )
                if tripped:
                    self.broker.cancel_all()
                    self.state.set_positions(self.broker.positions())
                    continue

                htf = resample_ohlcv(ltf, cfg.timeframes.ltf, cfg.timeframes.htf)
                if len(htf) < 30:
                    self.state.set_positions(self.broker.positions())
                    continue
                signals = self._strategy.on_bar(sym, ltf, htf)
                ctx = self._strategy._ctx_for(sym)  # noqa: SLF001
                scan_rows[sym] = ScanRow(
                    symbol=sym, bias=ctx.htf_bias, state=ctx.state,
                    target_price=ctx.htf_target_price,
                    last_close=float(ltf["close"].iloc[-1]), ts=last_close_ts,
                )
                if any(p.symbol == sym for p in self.broker.positions()):
                    continue
                for sig in signals:
                    qty = size_position(
                        equity=eq_value, risk_pct=cfg.risk.risk_pct_per_trade,
                        entry=sig.entry, stop_loss=sig.stop_loss,
                        spec=self._spec, max_leverage=cfg.risk.max_leverage,
                    )
                    if qty <= 0:
                        continue
                    if len(self.broker.positions()) >= cfg.risk.max_concurrent_positions:
                        break
                    cid = f"{sym}-{last_close_ts}"
                    self.broker.submit_smc_bracket(
                        symbol=sym, side=sig.side, qty=qty,
                        entry_price=sig.entry, stop_loss=sig.stop_loss,
                        take_profit_1=sig.take_profit_1,
                        take_profit_2=sig.take_profit_2,
                        partial_pct=cfg.strategy.partial_tp_pct,
                        client_id=cid,
                    )

            self.state.set_scan(scan_rows)
            self.state.set_positions(self.broker.positions())
            # newly-closed trades since last snapshot
            if hasattr(self.broker, "trades"):
                tracked_n = len(self.state.trades)
                for t in self.broker.trades()[tracked_n:]:
                    self.state.push_trade(t)

            self._stop_event.wait(min(ltf_step_ms / 1000, 5))
        log.info("Bot loop stopped")


_RUNTIME: BotRuntime | None = None
_RUNTIME_LOCK = threading.Lock()


def init_runtime(cfg: BotConfig) -> BotRuntime:
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = BotRuntime(cfg)
        return _RUNTIME


def get_runtime() -> BotRuntime:
    if _RUNTIME is None:
        raise RuntimeError("Runtime not initialized. Call init_runtime(cfg) first.")
    return _RUNTIME


def reset_runtime() -> None:
    """Test helper."""
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is not None:
            try:
                _RUNTIME.stop("reset")
            except Exception:  # noqa: BLE001
                pass
        _RUNTIME = None
