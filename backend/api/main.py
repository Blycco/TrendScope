"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from backend.api.admin_app import create_admin_app
from backend.api.middleware.plan_gate import PlanGateMiddleware
from backend.api.middleware.quota import QuotaMiddleware
from backend.api.middleware.rate_limit import RateLimitMiddleware
from backend.api.pubsub.trends_consumer import run_trends_consumer
from backend.api.routers import (
    auth,
    brand,
    compare,
    content,
    dashboard,
    early_trend,
    events,
    forecast,
    health,
    insights,
    keywords,
    live,
    meta_trends,
    news,
    notifications,
    payments,
    personalization,
    regional,
    scraps,
    settings,
    shares,
    subscriptions,
    trends,
)
from backend.api.routers.webhooks import payment as webhooks_payment
from backend.common.errors import set_error_log_pool
from backend.common.logging_config import setup_logging
from backend.jobs.audit_archive import register_archive_job
from backend.processor.shared.cache_manager import (
    close_pubsub,
    close_redis,
    init_pubsub,
    init_redis,
)

# --- Logging setup ---
setup_logging("api")

logger = structlog.get_logger(__name__)


def _get_required_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"Required environment variable not set: {key}")
    return value


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage DB pool and Redis pool lifecycle.

    After creating the DB pool, the same pool is propagated to the mounted
    admin sub-application so both apps share a single connection pool.
    """
    database_url = _get_required_env("DATABASE_URL")
    redis_url = _get_required_env("REDIS_URL")

    try:
        app.state.db_pool = await asyncpg.create_pool(
            dsn=database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        set_error_log_pool(app.state.db_pool)
        logger.info("db_pool_created")
    except Exception as exc:
        logger.error("db_pool_creation_failed", error=str(exc))
        raise

    # Propagate shared resources to the admin sub-application.
    admin_app.state.db_pool = app.state.db_pool
    logger.info("admin_app_db_pool_propagated")

    try:
        await init_redis(redis_url)
    except Exception as exc:
        logger.error("redis_init_failed", error=str(exc))
        raise

    try:
        await init_pubsub(redis_url)
    except Exception as exc:
        logger.error("redis_pubsub_init_failed", error=str(exc))
        raise

    scheduler = register_archive_job(app)
    scheduler.start()
    logger.info("audit_archive_scheduler_started")

    trends_consumer_task = asyncio.create_task(run_trends_consumer(app.state.db_pool))
    logger.info("trends_consumer_started")

    yield

    trends_consumer_task.cancel()
    try:
        await trends_consumer_task
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.warning("trends_consumer_shutdown_error", error=str(exc))
    logger.info("trends_consumer_stopped")

    scheduler.shutdown(wait=False)
    logger.info("audit_archive_scheduler_stopped")

    await app.state.db_pool.close()
    logger.info("db_pool_closed")

    await close_pubsub()
    logger.info("redis_pubsub_closed")

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
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(dashboard.router, prefix="/api/v1")
    app.include_router(meta_trends.router, prefix="/api/v1")
    app.include_router(compare.router, prefix="/api/v1")
    app.include_router(keywords.router, prefix="/api/v1")
    app.include_router(regional.router, prefix="/api/v1")
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
    app.include_router(content.router, prefix="/api/v1")
    app.include_router(personalization.router, prefix="/api/v1")
    app.include_router(brand.router, prefix="/api/v1")
    app.include_router(shares.router, prefix="/api/v1")
    app.include_router(forecast.router, prefix="/api/v1")
    app.include_router(webhooks_payment.router, prefix="/api/v1")
    app.include_router(live.router, prefix="/api/v1")

    # Mount admin sub-application at /admin.
    # All admin router prefixes are /v1, so final paths are /admin/v1/...
    app.mount("/admin", admin_app)

    Instrumentator().instrument(app).expose(app)

    return app


# Module-level admin sub-app so the lifespan can propagate DB pool to it.
admin_app = create_admin_app()
app = create_app()
