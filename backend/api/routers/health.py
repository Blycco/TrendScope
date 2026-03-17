"""Health check endpoint. GET /health → 200 with DB + Redis status."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()
logger = structlog.get_logger(__name__)


class HealthResponse(BaseModel):
    status: str
    db: str
    redis: str


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check(request: Request) -> HealthResponse:
    """Check API, DB, and Redis connectivity."""
    db_status = "unknown"
    redis_status = "unknown"

    # DB check
    try:
        pool = request.app.state.db_pool
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "ok"
    except Exception as exc:
        logger.error("health_check_db_failed", error=str(exc))
        db_status = "error"

    # Redis check
    try:
        from backend.processor.shared.cache_manager import get_redis

        await get_redis().ping()
        redis_status = "ok"
    except Exception as exc:
        logger.error("health_check_redis_failed", error=str(exc))
        redis_status = "error"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    logger.info("health_check", status=overall, db=db_status, redis=redis_status)

    return HealthResponse(status=overall, db=db_status, redis=redis_status)
