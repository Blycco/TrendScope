"""Scheduled job: reset daily API usage quotas for all users."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def run_quota_reset(pool: asyncpg.Pool) -> int:
    """Reset used_count to 0 and set reset_at to tomorrow midnight UTC.

    Targets rows whose reset_at is in the past (quota period has elapsed).

    Returns the number of rows reset.
    """
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE api_usage
                SET used_count = 0,
                    reset_at = date_trunc('day', now() AT TIME ZONE 'UTC')
                              + INTERVAL '1 day'
                WHERE reset_at <= now()
                """
            )

        # asyncpg returns "UPDATE N" string
        count = int(result.split()[-1]) if result else 0
        logger.info("quota_reset_job_complete", reset_count=count)
        return count
    except Exception as exc:
        logger.error("quota_reset_job_failed", error=str(exc))
        raise
