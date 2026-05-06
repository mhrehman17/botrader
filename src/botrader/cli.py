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


@app.command()
def serve(
    config: Path = typer.Option(..., "--config", "-c", exists=True),
    host: str = typer.Option("127.0.0.1", help="Bind host. Use 0.0.0.0 for LAN access."),
    port: int = typer.Option(8787, help="Bind port."),
) -> None:
    """Run the HTTP API. Pairs with the mobile app."""
    cfg = load_config(config)
    log = setup_logging(cfg.logging.level)
    log.info(_BANNER)
    import os
    if not os.environ.get("BOTRADER_API_TOKEN"):
        log.error("BOTRADER_API_TOKEN is required. Generate with `openssl rand -hex 16`.")
        raise typer.Exit(code=2)
    if not os.environ.get("BOTRADER_MASTER_KEY"):
        log.warning(
            "BOTRADER_MASTER_KEY not set. Credential storage will fail. "
            "Generate one with `openssl rand -hex 32`."
        )
    import uvicorn

    from .api.app import create_app
    log.info("Starting API on http://%s:%d (mode=%s)", host, port, cfg.mode)
    uvicorn.run(create_app(cfg), host=host, port=port, log_level=cfg.logging.level.lower())


credentials_app = typer.Typer(help="Manage encrypted exchange API credentials.")
app.add_typer(credentials_app, name="credentials")


@credentials_app.command("add")
def credentials_add(
    exchange_id: str = typer.Argument(..., help="ccxt exchange id, e.g. binanceusdm."),
    testnet: bool = typer.Option(
        True, "--testnet/--mainnet", help="Whether this key is for testnet.",
    ),
    label: str = typer.Option("", help="Optional label for this credential."),
) -> None:
    """Interactively add an exchange credential to the encrypted store."""
    setup_logging("INFO")
    from .api import secrets_store
    api_key = typer.prompt(f"{exchange_id} API key")
    api_secret = typer.prompt(f"{exchange_id} API secret", hide_input=True)
    secrets_store.upsert(secrets_store.Credential(
        exchange_id=exchange_id,
        api_key=api_key, api_secret=api_secret,
        testnet=testnet, label=label,
    ))
    typer.echo(f"Saved {exchange_id} (testnet={testnet}).")


@credentials_app.command("list")
def credentials_list() -> None:
    """List configured exchange credentials (no secrets shown)."""
    setup_logging("WARNING")
    from .api import secrets_store
    for v in secrets_store.public_view_all():
        typer.echo(f"{v['id']}\ttestnet={v['testnet']}\tlabel={v.get('label','')}")


@credentials_app.command("rm")
def credentials_rm(exchange_id: str) -> None:
    """Remove a credential."""
    setup_logging("INFO")
    from .api import secrets_store
    if secrets_store.delete(exchange_id):
        typer.echo(f"Removed {exchange_id}.")
    else:
        typer.echo(f"No credential for {exchange_id}.", err=True)
        raise typer.Exit(code=1)


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted.\n")
        sys.exit(130)


if __name__ == "__main__":
    main()
