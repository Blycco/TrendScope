"""Insight quota checking dependency. (RULE 09: api_usage check, RULE 02: asyncpg $1,$2)"""

from __future__ import annotations

from datetime import datetime, timezone

import asyncpg
import structlog
from fastapi import Depends, Request

from backend.auth.dependencies import CurrentUser, require_auth
from backend.common.errors import ErrorCode, http_error

logger = structlog.get_logger(__name__)

_FREE_DAILY_LIMIT = 3  # free plan: 3 insights/day
_PAID_DAILY_LIMIT = 0  # 0 = unlimited for pro/business/enterprise

_INSIGHT_ENDPOINT = "insights"


async def check_insight_quota(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> CurrentUser:
    """FastAPI dependency: enforce daily insight quota for free-plan users.

    Pro/business/enterprise plans are unlimited and bypass the check.
    Raises 429 when the free quota is exhausted, 500 on DB error.
    """
    if current_user.plan in ("pro", "business", "enterprise"):
        return current_user

    now_utc = datetime.now(tz=timezone.utc)
    reset_at = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    pool: asyncpg.Pool = request.app.state.db_pool

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO api_usage (user_id, endpoint, used_count, quota_limit, reset_at)
                VALUES ($1, $2, 0, $3, $4)
                ON CONFLICT (user_id, endpoint, reset_at) DO NOTHING
                """,
                current_user.user_id,
                _INSIGHT_ENDPOINT,
                _FREE_DAILY_LIMIT,
                reset_at,
            )

            row = await conn.fetchrow(
                """
                SELECT used_count, quota_limit
                FROM api_usage
                WHERE user_id = $1
                  AND endpoint = $2
                  AND reset_at = $3
                """,
                current_user.user_id,
                _INSIGHT_ENDPOINT,
                reset_at,
            )

        if row and row["quota_limit"] > 0 and row["used_count"] >= row["quota_limit"]:
            raise http_error(
                ErrorCode.QUOTA_EXCEEDED,
                "Daily insight quota exceeded",
                status_code=429,
            )

    except Exception as exc:
        if getattr(exc, "status_code", None) == 429:
            raise
        logger.warning(
            "quota_check_failed",
            user_id=current_user.user_id,
            error=str(exc),
        )
        raise http_error(ErrorCode.DB_ERROR, "Quota check failed", status_code=500) from exc

    return current_user


async def increment_insight_usage(
    pool: asyncpg.Pool,
    user_id: str,
    reset_at: datetime,
) -> None:
    """Best-effort increment of insight usage counter after a successful request."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE api_usage
                SET used_count = used_count + 1
                WHERE user_id = $1
                  AND endpoint = $2
                  AND reset_at = $3
                """,
                user_id,
                _INSIGHT_ENDPOINT,
                reset_at,
            )
    except Exception as exc:
        logger.warning(
            "increment_insight_usage_failed",
            user_id=user_id,
            error=str(exc),
        )
