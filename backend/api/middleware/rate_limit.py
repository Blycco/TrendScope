"""Rate limit middleware — IP/user-based request throttling. (RULE 06, 07)"""

from __future__ import annotations

import os
import time

import structlog
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.auth.dependencies import CurrentUser, require_auth
from backend.auth.jwt import decode_token
from backend.common.errors import ErrorCode
from backend.processor.shared.cache_manager import get_redis

logger = structlog.get_logger(__name__)

# req/min limits
_LIMIT_ANONYMOUS = 60
_LIMIT_AUTHENTICATED = 300
_LIMIT_EVENTS = 600
_WINDOW_SECONDS = 60


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _extract_user_id(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer ") :]
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except Exception:
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001, ANN201
        disabled = os.environ.get("RATE_LIMIT_DISABLED", "false").lower() == "true"
        is_production = os.environ.get("APP_ENV", "").lower() == "production"
        if disabled and is_production:
            logger.warning("rate_limit_disabled_ignored_in_production")
        elif disabled:
            return await call_next(request)
        try:
            path = request.url.path
            user_id = _extract_user_id(request)
            client_ip = _get_client_ip(request)

            if path.startswith("/api/v1/events") and user_id:
                redis_key = f"ratelimit:events:{user_id}"
                limit = _LIMIT_EVENTS
            elif user_id:
                redis_key = f"ratelimit:user:{user_id}"
                limit = _LIMIT_AUTHENTICATED
            else:
                redis_key = f"ratelimit:ip:{client_ip}"
                limit = _LIMIT_ANONYMOUS

            redis = get_redis()
            current: bytes | None = await redis.get(redis_key)
            count = int(current) if current else 0

            if count >= limit:
                ttl: int = await redis.ttl(redis_key)
                retry_after = max(ttl, 1)
                logger.warning(
                    "rate_limit_exceeded",
                    key=redis_key,
                    count=count,
                    limit=limit,
                    retry_after=retry_after,
                )
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                    content={
                        "code": ErrorCode.FORBIDDEN.value,
                        "message": "Rate limit exceeded",
                        "message_key": "error.rate_limit_exceeded",
                        "retry_after": retry_after,
                    },
                )

            pipe = redis.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, _WINDOW_SECONDS, nx=True)
            await pipe.execute()

            return await call_next(request)
        except Exception as exc:
            logger.error("rate_limit_middleware_error", error=str(exc), path=request.url.path)
            # fail open — don't block requests on Redis errors
            return await call_next(request)


# ---------------------------------------------------------------------------
# FastAPI dependency function (used by individual route handlers via Depends)
# ---------------------------------------------------------------------------

_DEP_RATE_LIMIT = 300  # req/min per authenticated user
_DEP_WINDOW_SECONDS = 60


async def rate_limit_check(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> CurrentUser:
    """FastAPI dependency: enforce 300 req/min per user via Redis INCR.

    Fails open on Redis error to preserve availability.
    """
    try:
        redis = get_redis()
        minute_bucket = int(time.time()) // _DEP_WINDOW_SECONDS
        key = f"ratelimit:{current_user.user_id}:{minute_bucket}"

        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, _DEP_WINDOW_SECONDS)

        if count > _DEP_RATE_LIMIT:
            retry_after = _DEP_WINDOW_SECONDS - (int(time.time()) % _DEP_WINDOW_SECONDS)
            raise HTTPException(
                status_code=429,
                detail={
                    "code": ErrorCode.FORBIDDEN.value,
                    "message": "Rate limit exceeded",
                    "retry_after": retry_after,
                },
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(
            "rate_limit_dep_redis_error",
            user_id=current_user.user_id,
            error=str(exc),
        )

    return current_user
