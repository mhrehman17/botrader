"""Paper broker — same fill model as SimBroker, but driven by live OHLCV."""
from __future__ import annotations

from .sim_broker import SimBroker


class PaperBroker(SimBroker):
    """Identical to SimBroker; the runner feeds it live closed bars."""

    pass
