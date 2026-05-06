"""FastAPI app factory."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import BotConfig
from .routers import account, bot, credentials, market, scanner, system, trades
from .runtime import init_runtime

log = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    if not os.environ.get("BOTRADER_API_TOKEN"):
        log.error("BOTRADER_API_TOKEN is not set. All requests will fail with 503.")
    yield
    # shutdown: stop the bot loop if running
    from .runtime import get_runtime
    try:
        get_runtime().stop("shutdown")
    except Exception:  # noqa: BLE001
        pass


def create_app(cfg: BotConfig) -> FastAPI:
    app = FastAPI(
        title="botrader",
        description="HTTP API for the SMC crypto futures bot.",
        version="0.1.0",
        lifespan=_lifespan,
    )
    # Permissive CORS — the API is bearer-token-protected, and the mobile
    # app will run on arbitrary local IPs during development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # init runtime singleton
    init_runtime(cfg)

    app.include_router(system.router, tags=["system"])
    app.include_router(account.router, tags=["account"])
    app.include_router(trades.router, tags=["trades"])
    app.include_router(scanner.router, tags=["scanner"])
    app.include_router(market.router, tags=["market"])
    app.include_router(bot.router, tags=["bot"])
    app.include_router(credentials.router, tags=["credentials"])

    return app
