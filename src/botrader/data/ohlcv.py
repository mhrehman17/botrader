"""OHLCV data layer: ccxt fetcher + parquet cache.

Cache layout: <cache_dir>/<exchange_id>/<symbol_safe>_<tf>.parquet
Idempotent: re-running `fetch_and_cache` only fetches missing tail bars.
"""
from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ..utils.timeframes import tf_to_ms

log = logging.getLogger(__name__)


def _safe_symbol(symbol: str) -> str:
    return symbol.replace("/", "-").replace(":", "_")


def cache_path(cache_dir: Path | str, exchange: str, symbol: str, tf: str) -> Path:
    return Path(cache_dir) / exchange / f"{_safe_symbol(symbol)}_{tf}.parquet"


def _iso_to_ms(s: str) -> int:
    dt = datetime.fromisoformat(s).replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


def _to_df(rows: list[list[float]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = df["ts"].astype("int64")
    df = df.drop_duplicates(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    return df


def load_cache(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
    return pd.read_parquet(path)


def save_cache(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _make_exchange(exchange_id: str):
    """Lazy import ccxt and instantiate a public client (no keys needed for OHLCV)."""
    import ccxt  # noqa: PLC0415  — keep CLI startup fast

    klass = getattr(ccxt, exchange_id, None)
    if klass is None:
        raise ValueError(f"Unknown ccxt exchange id: {exchange_id!r}")
    ex = klass({"enableRateLimit": True})
    if hasattr(ex, "load_markets"):
        ex.load_markets()
    return ex


def fetch_ohlcv_range(
    exchange_id: str,
    symbol: str,
    timeframe: str,
    since_ms: int,
    until_ms: int | None = None,
    limit: int = 1500,
    max_retries: int = 5,
) -> pd.DataFrame:
    """Fetch OHLCV from `since_ms` (inclusive) up to `until_ms` (exclusive, or now)."""
    ex = _make_exchange(exchange_id)
    step = tf_to_ms(timeframe)
    until_ms = until_ms or int(time.time() * 1000)
    rows: list[list[float]] = []
    cursor = since_ms

    while cursor < until_ms:
        attempt = 0
        while True:
            try:
                batch = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=limit)
                break
            except Exception as e:  # noqa: BLE001 — retry network-ish errors
                attempt += 1
                if attempt > max_retries:
                    raise
                wait = min(60, 2**attempt)
                log.warning("fetch_ohlcv failed (%s); retry %d in %ds", e, attempt, wait)
                time.sleep(wait)

        if not batch:
            break
        rows.extend(batch)
        last_ts = batch[-1][0]
        next_cursor = last_ts + step
        if next_cursor <= cursor:  # no progress
            break
        cursor = next_cursor
        # respect rate limit
        time.sleep(getattr(ex, "rateLimit", 200) / 1000.0)

    df = _to_df(rows)
    if not df.empty:
        df = df[df["ts"] < until_ms].reset_index(drop=True)
    return df


def fetch_and_cache(
    exchange_id: str,
    symbol: str,
    timeframe: str,
    since: str,
    until: str | None,
    cache_dir: Path | str,
) -> int:
    """Fetch OHLCV and merge into parquet cache. Returns total rows in cache after merge."""
    path = cache_path(cache_dir, exchange_id, symbol, timeframe)
    existing = load_cache(path)
    since_ms = _iso_to_ms(since)
    until_ms = _iso_to_ms(until) if until else int(time.time() * 1000)

    if not existing.empty:
        # only fetch the missing tail past existing.ts.max()
        last_ts = int(existing["ts"].max())
        since_ms = max(since_ms, last_ts + tf_to_ms(timeframe))
        if since_ms >= until_ms:
            log.info("Cache already up-to-date for %s %s %s (%d rows)",
                     exchange_id, symbol, timeframe, len(existing))
            return len(existing)

    log.info("Fetching %s %s %s from %s to %s",
             exchange_id, symbol, timeframe,
             datetime.fromtimestamp(since_ms / 1000, tz=UTC).isoformat(),
             datetime.fromtimestamp(until_ms / 1000, tz=UTC).isoformat())

    new_df = fetch_ohlcv_range(exchange_id, symbol, timeframe, since_ms, until_ms)
    if new_df.empty:
        return len(existing)

    merged = (
        pd.concat([existing, new_df], ignore_index=True)
        .drop_duplicates(subset=["ts"])
        .sort_values("ts")
        .reset_index(drop=True)
    )
    save_cache(merged, path)
    return len(merged)


def load_range(
    cache_dir: Path | str,
    exchange_id: str,
    symbol: str,
    timeframe: str,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> pd.DataFrame:
    """Load a date-bounded slice from the parquet cache. Empty df if no cache."""
    df = load_cache(cache_path(cache_dir, exchange_id, symbol, timeframe))
    if df.empty:
        return df
    if start_ms is not None:
        df = df[df["ts"] >= start_ms]
    if end_ms is not None:
        df = df[df["ts"] < end_ms]
    return df.reset_index(drop=True)
