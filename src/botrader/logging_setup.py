"""Logging configuration. Uses rich for pretty console output, plain for files."""
from __future__ import annotations

import logging
from pathlib import Path

from rich.logging import RichHandler


def setup_logging(level: str = "INFO", run_dir: Path | None = None) -> logging.Logger:
    """Configure root logger. If run_dir is given, also write botrader.log there."""
    handlers: list[logging.Handler] = [
        RichHandler(rich_tracebacks=True, show_time=True, show_path=False, markup=False),
    ]
    if run_dir is not None:
        run_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(run_dir / "botrader.log")
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        handlers.append(fh)

    logging.basicConfig(
        level=level.upper(),
        format="%(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
        force=True,
    )
    # Quiet noisy libs
    for noisy in ("ccxt", "urllib3", "websockets", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logging.getLogger("botrader")
