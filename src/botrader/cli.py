"""botrader CLI."""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import typer

from .config import BotConfig, load_config
from .logging_setup import setup_logging

app = typer.Typer(
    name="botrader",
    help="Smart Money Concepts (SMC) day-trading bot for crypto futures.",
    no_args_is_help=True,
    add_completion=False,
)


_BANNER = (
    "[botrader] WARNING: trading bots can lose money. Backtest, walk-forward, "
    "paper-trade, and use testnet before mainnet. The authors are not liable for losses."
)


def _make_run_dir(prefix: str) -> Path:
    ts = datetime.now(UTC).strftime("%Y-%m-%d_%H%M%S")
    p = Path("runs") / f"{prefix}_{ts}"
    p.mkdir(parents=True, exist_ok=True)
    return p


@app.command()
def backtest(
    config: Path = typer.Option(..., "--config", "-c", exists=True, help="Config YAML."),
) -> None:
    """Run a backtest using cached OHLCV data."""
    cfg: BotConfig = load_config(config)
    run_dir = _make_run_dir("backtest")
    log = setup_logging(cfg.logging.level, run_dir)
    log.info(_BANNER)
    log.info("Mode=%s symbols=%s timeframes=%s/%s",
             cfg.mode, cfg.symbols, cfg.timeframes.htf, cfg.timeframes.ltf)

    # Lazy import to keep CLI import-time light.
    from .runner.mode import run_backtest

    result = run_backtest(cfg, run_dir)
    log.info("Backtest complete. Trades=%d  Final equity=%.2f",
             len(result.trades),
             result.equity_curve[-1].equity if result.equity_curve else cfg.backtest.initial_equity)
    log.info("Run artifacts: %s", run_dir)


@app.command()
def paper(
    config: Path = typer.Option(..., "--config", "-c", exists=True, help="Config YAML."),
) -> None:
    """Paper-trade against live exchange data."""
    cfg = load_config(config)
    run_dir = _make_run_dir("paper")
    log = setup_logging(cfg.logging.level, run_dir)
    log.info(_BANNER)
    if cfg.mode != "paper":
        log.warning("Config mode=%s but the `paper` command was used; running paper.", cfg.mode)
    from .runner.live import run_live
    run_live(cfg, run_dir, mode="paper")


@app.command()
def live(
    config: Path = typer.Option(..., "--config", "-c", exists=True, help="Config YAML."),
    i_understand_the_risks: bool = typer.Option(
        False,
        "--i-understand-the-risks",
        help="Required to run on mainnet (real funds). Read the README first.",
    ),
    force_signal: str | None = typer.Option(
        None, "--force-signal", help="(testing) Force one signal: 'long' or 'short'."
    ),
) -> None:
    """Live trading on testnet (default) or mainnet (gated)."""
    cfg = load_config(config)
    run_dir = _make_run_dir("live")
    log = setup_logging(cfg.logging.level, run_dir)
    log.info(_BANNER)

    is_mainnet = cfg.mode == "mainnet" or (cfg.mode == "testnet" and not cfg.exchange.testnet)
    if is_mainnet and not i_understand_the_risks:
        log.error(
            "Mainnet requested but --i-understand-the-risks not passed. Refusing to start."
        )
        raise typer.Exit(code=2)

    from .runner.live import run_live
    mode = "mainnet" if is_mainnet else "testnet"
    run_live(cfg, run_dir, mode=mode, force_signal=force_signal)


@app.command("fetch-data")
def fetch_data(
    exchange: str = typer.Option("binanceusdm", help="ccxt exchange id."),
    symbol: str = typer.Option(..., help="Symbol, e.g. 'BTC/USDT:USDT'."),
    tf: str = typer.Option(..., "--tf", help="Timeframe e.g. '5m', '1h'."),
    since: str = typer.Option(..., help="ISO date 'YYYY-MM-DD'."),
    until: str | None = typer.Option(None, help="ISO date 'YYYY-MM-DD' (default: now)."),
    cache_dir: Path = typer.Option(Path(".cache/ohlcv"), help="Parquet cache dir."),
) -> None:
    """Download historical OHLCV to the parquet cache."""
    log = setup_logging("INFO")
    from .data.ohlcv import fetch_and_cache
    n = fetch_and_cache(exchange, symbol, tf, since, until, cache_dir)
    log.info("Cached %d bars for %s %s %s in %s", n, exchange, symbol, tf, cache_dir)


@app.command()
def scan(
    config: Path = typer.Option(..., "--config", "-c", exists=True),
    once: bool = typer.Option(True, help="Print one snapshot and exit."),
) -> None:
    """Print current SMC state for the configured symbols (no orders)."""
    cfg = load_config(config)
    setup_logging(cfg.logging.level)
    from .runner.live import run_scan
    run_scan(cfg, once=once)


@app.command()
def report(
    run_dir: Path = typer.Option(..., "--run-dir", exists=True, file_okay=False),
) -> None:
    """Regenerate metrics + plots for a backtest run directory."""
    setup_logging("INFO")
    from .backtest.report import regenerate_report
    regenerate_report(run_dir)


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted.\n")
        sys.exit(130)


if __name__ == "__main__":
    main()
