"""Resample LTF candles to HTF."""
from __future__ import annotations

import pandas as pd

from ..utils.timeframes import tf_to_ms


def resample_ohlcv(df: pd.DataFrame, source_tf: str, target_tf: str) -> pd.DataFrame:
    """Resample OHLCV from source_tf to target_tf (target must be >= source)."""
    src_ms = tf_to_ms(source_tf)
    tgt_ms = tf_to_ms(target_tf)
    if tgt_ms < src_ms:
        raise ValueError(f"target {target_tf} smaller than source {source_tf}")
    if df.empty:
        return df.copy()

    tmp = df.copy()
    tmp["dt"] = pd.to_datetime(tmp["ts"], unit="ms", utc=True)
    tmp = tmp.set_index("dt")
    rule = _to_pandas_rule(target_tf)
    agg = tmp.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna(subset=["open"])
    agg = agg.reset_index()
    agg["ts"] = (agg["dt"].astype("int64") // 1_000_000).astype("int64")
    return agg[["ts", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


def _to_pandas_rule(tf: str) -> str:
    unit = tf[-1].lower()
    n = int(tf[:-1])
    return {
        "s": f"{n}s",
        "m": f"{n}min",
        "h": f"{n}h",
        "d": f"{n}D",
        "w": f"{n}W",
    }[unit]
