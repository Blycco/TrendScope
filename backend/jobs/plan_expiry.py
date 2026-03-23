"""Scheduled job: expire overdue subscriptions and downgrade user plan to free."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def run_plan_expiry(pool: asyncpg.Pool) -> int:
    """Find active subscriptions past their expires_at and mark them expired.

    Also downgrades the corresponding user_profile.plan to 'free'.

    Returns the number of subscriptions expired.
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                UPDATE subscription
                SET status = 'expired', updated_at = now()
                WHERE status = 'active'
                  AND expires_at IS NOT NULL
                  AND expires_at < now()
                RETURNING id::text, user_id::text
                """
            )

        if not rows:
            logger.info("plan_expiry_job_no_rows")
            return 0

        user_ids = list({row["user_id"] for row in rows})
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                UPDATE user_profile
                SET plan = 'free', updated_at = now()
                WHERE id = $1::uuid AND plan != 'free'
                """,
                [(uid,) for uid in user_ids],
            )

        logger.info("plan_expiry_job_complete", expired_count=len(rows))
        return len(rows)
    except Exception as exc:
        logger.error("plan_expiry_job_failed", error=str(exc))
        raise
