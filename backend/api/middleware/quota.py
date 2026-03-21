"""Quota middleware — daily API usage tracking and enforcement. (RULE 09)"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import asyncpg
import structlog
from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.auth.dependencies import CurrentUser, require_auth
from backend.auth.jwt import decode_token
from backend.common.errors import ErrorCode, http_error

logger = structlog.get_logger(__name__)

# (path_prefix, plan_level) → daily limit; None = unlimited; -1 = blocked entirely
# plan_level: 0=free, 1=pro, 2=business, 3=enterprise
_QUOTA_TABLE: list[tuple[str, int, int | None]] = [
    # path_prefix, max_plan_level_inclusive, limit
    # /api/v1/trends — free: 10/day, pro+: unlimited
    ("/api/v1/trends", 0, 10),
    ("/api/v1/trends", 1, None),
    ("/api/v1/trends", 2, None),
    ("/api/v1/trends", 3, None),
    # /api/v1/scraps — free: 50 total (tracked as daily for simplicity), pro+: unlimited
    ("/api/v1/scraps", 0, 50),
    ("/api/v1/scraps", 1, None),
    ("/api/v1/scraps", 2, None),
    ("/api/v1/scraps", 3, None),
    # /api/v1/content/ideas — free: blocked, pro: 5/day, business+: unlimited
    ("/api/v1/content/ideas", 0, -1),
    ("/api/v1/content/ideas", 1, 5),
    ("/api/v1/content/ideas", 2, None),
    ("/api/v1/content/ideas", 3, None),
]

_PLAN_LEVEL: dict[str, int] = {
    "free": 0,
    "pro": 1,
    "business": 2,
    "enterprise": 3,
}

_QUOTA_TYPE_MAP: dict[str, str] = {
    "/api/v1/trends": "daily_trends",
    "/api/v1/scraps": "daily_scraps",
    "/api/v1/content/ideas": "daily_content_ideas",
}

_GATED_METHODS = {"POST", "GET"}


def _extract_user_info(request: Request) -> tuple[str | None, str]:
    """Return (user_id, plan) from Bearer JWT."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, "free"
    token = auth_header[len("Bearer ") :]
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None, "free"
        return payload.get("sub"), payload.get("plan", "free")
    except Exception:
        return None, "free"


def _get_quota_limit(path: str, plan_level: int) -> tuple[str | None, int | None]:
    """Return (quota_type, limit) for the given path and plan level.

    limit=None means unlimited; limit=-1 means fully blocked.
    Returns (None, None) if this path is not quota-gated.
    """
    matched_prefix: str | None = None
    for prefix, level, limit in _QUOTA_TABLE:
        if path.startswith(prefix):
            matched_prefix = prefix
            if level == plan_level:
                quota_type = _QUOTA_TYPE_MAP.get(prefix, prefix)
                return quota_type, limit

    if matched_prefix is None:
        return None, None

    # fallback: unlimited for unmatched levels above table
    quota_type = _QUOTA_TYPE_MAP.get(matched_prefix, matched_prefix)
    return quota_type, None


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class QuotaMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001, ANN201
        if os.environ.get("QUOTA_DISABLED", "false").lower() == "true":
            return await call_next(request)
        try:
            if request.method not in _GATED_METHODS:
                return await call_next(request)

            user_id, plan = _extract_user_info(request)
            plan_level = _PLAN_LEVEL.get(plan, 0)
            path = request.url.path

            quota_type, limit = _get_quota_limit(path, plan_level)

            if quota_type is None:
                # not a quota-gated path
                return await call_next(request)

            if limit == -1:
                logger.info(
                    "quota_blocked_plan",
                    path=path,
                    plan=plan,
                    quota_type=quota_type,
                )
                reset_at = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "error_code": ErrorCode.QUOTA_EXCEEDED.value,
                        "message_key": "error.quota_exceeded",
                        "quota_type": quota_type,
                        "limit": 0,
                        "reset_at": reset_at.isoformat(),
                        "upgrade_url": "/pricing",
                    },
                )

            if limit is None:
                # unlimited
                return await call_next(request)

            # check against DB
            db_pool = request.app.state.db_pool
            today = _today_utc()

            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT usage_count FROM api_usage
                    WHERE user_id = $1
                      AND quota_type = $2
                      AND usage_date = $3
                    """,
                    user_id,
                    quota_type,
                    today,
                )
                current_usage = row["usage_count"] if row else 0

                if current_usage >= limit:
                    reset_at = datetime.now(timezone.utc).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    logger.warning(
                        "quota_exceeded",
                        user_id=user_id,
                        quota_type=quota_type,
                        current=current_usage,
                        limit=limit,
                    )
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error_code": ErrorCode.QUOTA_EXCEEDED.value,
                            "message_key": "error.quota_exceeded",
                            "quota_type": quota_type,
                            "limit": limit,
                            "reset_at": reset_at.isoformat(),
                            "upgrade_url": "/pricing",
                        },
                    )

            response = await call_next(request)

            # increment usage counter after successful response
            if response.status_code < 400:
                async with db_pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO api_usage (user_id, quota_type, usage_date, usage_count)
                        VALUES ($1, $2, $3, 1)
                        ON CONFLICT (user_id, quota_type, usage_date)
                        DO UPDATE SET usage_count = api_usage.usage_count + 1
                        """,
                        user_id,
                        quota_type,
                        today,
                    )

            return response
        except Exception as exc:
            logger.error("quota_middleware_error", error=str(exc), path=request.url.path)
            return JSONResponse(
                status_code=500,
                content={
                    "code": ErrorCode.INTERNAL_ERROR.value,
                    "message": "Internal server error",
                    "message_key": "error.internal",
                },
            )


# ---------------------------------------------------------------------------
# FastAPI dependency functions (used by individual route handlers via Depends)
# ---------------------------------------------------------------------------

_FREE_DAILY_INSIGHT_LIMIT = 3
_INSIGHT_ENDPOINT = "insights"


async def check_insight_quota(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> CurrentUser:
    """FastAPI dependency: enforce daily insight quota for free-plan users.

    Pro/business/enterprise plans bypass the check (unlimited).
    Raises 429 when quota is exhausted, 500 on DB error.
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
                _FREE_DAILY_INSIGHT_LIMIT,
                reset_at,
            )
            row = await conn.fetchrow(
                """
                SELECT used_count, quota_limit FROM api_usage
                WHERE user_id = $1 AND endpoint = $2 AND reset_at = $3
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
        logger.warning("quota_check_failed", user_id=current_user.user_id, error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Quota check failed", status_code=500) from exc

    return current_user
