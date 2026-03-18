"""Rate limiting dependency: 300 req/min per user via Redis INCR.

RULE 03: async. RULE 06: try/except.
"""

from __future__ import annotations

import time

import structlog
from fastapi import Depends, HTTPException, Request

from backend.auth.dependencies import CurrentUser, require_auth
from backend.processor.shared.cache_manager import get_redis

logger = structlog.get_logger(__name__)

_RATE_LIMIT = 300  # requests per minute
_WINDOW_SECONDS = 60  # 1 minute bucket


async def rate_limit_check(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> CurrentUser:
    """FastAPI dependency: enforce 300 req/min per user via Redis INCR.

    Fails open on Redis error to preserve availability.
    """
    try:
        redis = get_redis()
        minute_bucket = int(time.time()) // _WINDOW_SECONDS
        key = f"ratelimit:{current_user.user_id}:{minute_bucket}"

        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, _WINDOW_SECONDS)

        if count > _RATE_LIMIT:
            retry_after = _WINDOW_SECONDS - (int(time.time()) % _WINDOW_SECONDS)
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "E0041",
                    "message": "Rate limit exceeded",
                    "retry_after": retry_after,
                },
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(
            "rate_limit_redis_error",
            user_id=current_user.user_id,
            error=str(exc),
        )

    return current_user
