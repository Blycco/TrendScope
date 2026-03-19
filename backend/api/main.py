"""FastAPI application entry point."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
import structlog
import structlog.stdlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.middleware.plan_gate import PlanGateMiddleware
from backend.api.middleware.quota import QuotaMiddleware
from backend.api.middleware.rate_limit import RateLimitMiddleware
from backend.api.routers import (
    auth,
    early_trend,
    events,
    health,
    insights,
    news,
    notifications,
    payments,
    scraps,
    settings,
    subscriptions,
    trends,
)
from backend.api.routers.webhooks import payment as webhooks_payment
from backend.processor.shared.cache_manager import close_redis, init_redis

# --- Logging setup ---
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger(__name__)


def _get_required_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"Required environment variable not set: {key}")
    return value


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage DB pool and Redis pool lifecycle."""
    database_url = _get_required_env("DATABASE_URL")
    redis_url = _get_required_env("REDIS_URL")

    try:
        app.state.db_pool = await asyncpg.create_pool(
            dsn=database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("db_pool_created")
    except Exception as exc:
        logger.error("db_pool_creation_failed", error=str(exc))
        raise

    try:
        await init_redis(redis_url)
    except Exception as exc:
        logger.error("redis_init_failed", error=str(exc))
        raise

    yield

    await app.state.db_pool.close()
    logger.info("db_pool_closed")

    await close_redis()
    logger.info("redis_pool_closed")


def create_app() -> FastAPI:
    app = FastAPI(
        title="TrendScope API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware execution order: CORS → RateLimit → PlanGate → Quota → route
    # last-added = outermost = first-executed
    app.add_middleware(QuotaMiddleware)  # innermost (added 1st)
    app.add_middleware(PlanGateMiddleware)  # middle
    app.add_middleware(RateLimitMiddleware)  # after CORS

    allowed_origins = os.environ.get("ALLOWED_ORIGINS", "").split(",")
    app.add_middleware(  # outermost (added last = runs first)
        CORSMiddleware,
        allow_origins=[o.strip() for o in allowed_origins if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(trends.router, prefix="/api/v1")
    app.include_router(early_trend.router, prefix="/api/v1")
    app.include_router(insights.router, prefix="/api/v1")
    app.include_router(news.router, prefix="/api/v1")
    app.include_router(scraps.router, prefix="/api/v1")
    app.include_router(settings.router, prefix="/api/v1")
    app.include_router(events.router, prefix="/api/v1")
    app.include_router(subscriptions.router, prefix="/api/v1")
    app.include_router(payments.router, prefix="/api/v1")
    app.include_router(notifications.router, prefix="/api/v1")
    app.include_router(webhooks_payment.router, prefix="/api/v1")

    return app


app = create_app()
