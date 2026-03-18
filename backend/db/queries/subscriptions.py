"""DB query layer for subscription table. (RULE 02: asyncpg $1,$2)"""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def get_current_subscription(
    pool: asyncpg.Pool,
    *,
    user_id: str,
) -> asyncpg.Record | None:
    """Return the most recent active subscription for a user."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT id::text, user_id::text, plan, status, provider,
                       provider_sub_id, started_at, expires_at, created_at
                FROM subscription
                WHERE user_id = $1::uuid AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                user_id,
            )
    except Exception as exc:
        logger.error("get_current_subscription_failed", user_id=user_id, error=str(exc))
        raise


async def create_subscription(
    pool: asyncpg.Pool,
    *,
    user_id: str,
    plan: str,
    provider: str | None = None,
    provider_sub_id: str | None = None,
) -> asyncpg.Record:
    """Create a new subscription row and return it."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                """
                INSERT INTO subscription (user_id, plan, provider, provider_sub_id)
                VALUES ($1::uuid, $2, $3, $4)
                RETURNING id::text, user_id::text, plan, status, provider,
                          provider_sub_id, started_at, expires_at, created_at
                """,
                user_id,
                plan,
                provider,
                provider_sub_id,
            )
    except Exception as exc:
        logger.error("create_subscription_failed", user_id=user_id, error=str(exc))
        raise


async def cancel_subscription(
    pool: asyncpg.Pool,
    *,
    subscription_id: str,
    user_id: str,
) -> asyncpg.Record | None:
    """Mark a subscription as cancelled. Returns the updated row or None."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                """
                UPDATE subscription
                SET status = 'cancelled', updated_at = now()
                WHERE id = $1::uuid AND user_id = $2::uuid AND status = 'active'
                RETURNING id::text, user_id::text, plan, status, provider,
                          provider_sub_id, started_at, expires_at, created_at
                """,
                subscription_id,
                user_id,
            )
    except Exception as exc:
        logger.error("cancel_subscription_failed", subscription_id=subscription_id, error=str(exc))
        raise


async def update_subscription_by_provider_id(
    pool: asyncpg.Pool,
    *,
    provider_sub_id: str,
    status: str,
    plan: str | None = None,
) -> asyncpg.Record | None:
    """Update subscription status (and optionally plan) by provider subscription ID.

    Used by payment webhook handlers.
    """
    try:
        async with pool.acquire() as conn:
            if plan:
                return await conn.fetchrow(
                    """
                    UPDATE subscription
                    SET status = $1, plan = $2, updated_at = now()
                    WHERE provider_sub_id = $3
                    RETURNING id::text, user_id::text, plan, status, provider,
                              provider_sub_id, started_at, expires_at, created_at
                    """,
                    status,
                    plan,
                    provider_sub_id,
                )
            return await conn.fetchrow(
                """
                UPDATE subscription
                SET status = $1, updated_at = now()
                WHERE provider_sub_id = $2
                RETURNING id::text, user_id::text, plan, status, provider,
                          provider_sub_id, started_at, expires_at, created_at
                """,
                status,
                provider_sub_id,
            )
    except Exception as exc:
        logger.error(
            "update_subscription_by_provider_id_failed",
            provider_sub_id=provider_sub_id,
            error=str(exc),
        )
        raise
