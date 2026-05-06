"""Strategy abstract base class."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from ..core.types import Signal


class Strategy(ABC):
    """A strategy turns multi-timeframe candle history into Signals.

    Implementations should be **pure** of side effects: same input -> same output.
    The engine handles persistence, broker calls, and equity accounting.
    """

    @abstractmethod
    def on_bar(
        self,
        symbol: str,
        ltf_df: pd.DataFrame,
        htf_df: pd.DataFrame,
    ) -> list[Signal]:
        """Called once per closed LTF bar. Return any new signals to act on."""
