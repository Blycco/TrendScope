"""DB query layer for admin operations. (RULE 02: asyncpg $1,$2 parameterization)"""

from __future__ import annotations

import json
from datetime import datetime

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


# --- User Management ---
async def admin_list_users(
    pool: asyncpg.Pool,
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[asyncpg.Record], int]:
    """List users with optional search and pagination."""
    try:
        async with pool.acquire() as conn:
            offset = (page - 1) * page_size
            if search:
                pattern = f"%{search}%"
                total = await conn.fetchval(
                    """
                    SELECT count(*) FROM user_profile
                    WHERE email ILIKE $1 OR display_name ILIKE $1
                    """,
                    pattern,
                )
                rows = await conn.fetch(
                    """
                    SELECT id::text, email, display_name, role, plan, locale, is_active, created_at
                    FROM user_profile
                    WHERE email ILIKE $1 OR display_name ILIKE $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    pattern,
                    page_size,
                    offset,
                )
            else:
                total = await conn.fetchval("SELECT count(*) FROM user_profile")
                rows = await conn.fetch(
                    """
                    SELECT id::text, email, display_name, role, plan, locale, is_active, created_at
                    FROM user_profile
                    ORDER BY created_at DESC
                    LIMIT $1 OFFSET $2
                    """,
                    page_size,
                    offset,
                )
            return rows, total or 0
    except Exception as exc:
        logger.error("admin_list_users_failed", error=str(exc))
        raise


async def admin_update_user(
    pool: asyncpg.Pool,
    user_id: str,
    *,
    plan: str | None = None,
    is_active: bool | None = None,
    role: str | None = None,
) -> asyncpg.Record | None:
    """Update user plan, is_active, or role."""
    allowed_fields: dict[str, object] = {}
    if plan is not None:
        allowed_fields["plan"] = plan
    if is_active is not None:
        allowed_fields["is_active"] = is_active
    if role is not None:
        allowed_fields["role"] = role

    if not allowed_fields:
        return None

    set_clauses: list[str] = []
    params: list[object] = [user_id]
    for idx, (col, val) in enumerate(allowed_fields.items(), start=2):
        set_clauses.append(f"{col} = ${idx}")
        params.append(val)

    # Safe: set_clauses built from whitelisted column names only (RULE 02)
    query = (
        f"UPDATE user_profile SET {', '.join(set_clauses)}, updated_at = now() "  # noqa: S608
        f"WHERE id = $1::uuid "
        f"RETURNING id::text, email, display_name, role, plan, locale, is_active, created_at"
    )
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *params)
    except Exception as exc:
        logger.error("admin_update_user_failed", user_id=user_id, error=str(exc))
        raise


async def admin_delete_user(pool: asyncpg.Pool, user_id: str) -> bool:
    """Delete a user by ID. Returns True if deleted."""
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM user_profile WHERE id = $1::uuid",
                user_id,
            )
            return result == "DELETE 1"
    except Exception as exc:
        logger.error("admin_delete_user_failed", user_id=user_id, error=str(exc))
        raise


# --- Subscriptions ---
async def admin_list_subscriptions(
    pool: asyncpg.Pool,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[asyncpg.Record], int]:
    """List all subscriptions with pagination."""
    try:
        async with pool.acquire() as conn:
            offset = (page - 1) * page_size
            total = await conn.fetchval("SELECT count(*) FROM subscription")
            rows = await conn.fetch(
                """
                SELECT id::text, user_id::text, plan, status, provider,
                       provider_sub_id, started_at, expires_at, created_at
                FROM subscription
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                page_size,
                offset,
            )
            return rows, total or 0
    except Exception as exc:
        logger.error("admin_list_subscriptions_failed", error=str(exc))
        raise


async def admin_refund_subscription(
    pool: asyncpg.Pool,
    subscription_id: str,
    reason: str,
) -> asyncpg.Record | None:
    """Mark subscription as refunded."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                """
                UPDATE subscription
                SET status = 'refunded', updated_at = now()
                WHERE id = $1::uuid AND status IN ('active', 'cancelled')
                RETURNING id::text, user_id::text, plan, status, provider,
                          provider_sub_id, started_at, expires_at, created_at
                """,
                subscription_id,
            )
    except Exception as exc:
        logger.error(
            "admin_refund_subscription_failed",
            subscription_id=subscription_id,
            error=str(exc),
        )
        raise


# --- Sources ---
async def admin_list_sources(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    """List all source_config entries."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT id::text, source_name, quota_limit, quota_used, is_active, updated_at
                FROM source_config
                ORDER BY source_name
                """
            )
    except Exception as exc:
        logger.error("admin_list_sources_failed", error=str(exc))
        raise


async def admin_update_source(
    pool: asyncpg.Pool,
    source_id: str,
    *,
    quota_limit: int | None = None,
    is_active: bool | None = None,
) -> asyncpg.Record | None:
    """Update source_config quota or active status."""
    fields: dict[str, object] = {}
    if quota_limit is not None:
        fields["quota_limit"] = quota_limit
    if is_active is not None:
        fields["is_active"] = is_active

    if not fields:
        return None

    set_clauses: list[str] = []
    params: list[object] = [source_id]
    for idx, (col, val) in enumerate(fields.items(), start=2):
        set_clauses.append(f"{col} = ${idx}")
        params.append(val)

    # Safe: set_clauses built from whitelisted column names only (RULE 02)
    query = (
        f"UPDATE source_config SET {', '.join(set_clauses)}, updated_at = now() "  # noqa: S608
        f"WHERE id = $1::uuid "
        f"RETURNING id::text, source_name, quota_limit, quota_used, is_active, updated_at"
    )
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *params)
    except Exception as exc:
        logger.error("admin_update_source_failed", source_id=source_id, error=str(exc))
        raise


async def admin_reset_source_quota(pool: asyncpg.Pool, source_id: str) -> asyncpg.Record | None:
    """Reset quota_used to 0 for a source."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                """
                UPDATE source_config SET quota_used = 0, updated_at = now()
                WHERE id = $1::uuid
                RETURNING id::text, source_name, quota_limit, quota_used, is_active, updated_at
                """,
                source_id,
            )
    except Exception as exc:
        logger.error("admin_reset_source_quota_failed", source_id=source_id, error=str(exc))
        raise


# --- Admin Settings ---
async def admin_get_settings(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    """Get all admin_settings rows."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT key, value, default_value, updated_at
                FROM admin_settings
                ORDER BY key
                """
            )
    except Exception as exc:
        logger.error("admin_get_settings_failed", error=str(exc))
        raise


async def admin_update_settings(
    pool: asyncpg.Pool,
    settings: dict[str, object],
) -> list[asyncpg.Record]:
    """Update multiple admin_settings values."""
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                for key, value in settings.items():
                    json_value = json.dumps(value)
                    await conn.execute(
                        """
                        UPDATE admin_settings SET value = $1::jsonb, updated_at = now()
                        WHERE key = $2
                        """,
                        json_value,
                        key,
                    )
            return await conn.fetch(
                "SELECT key, value, default_value, updated_at FROM admin_settings ORDER BY key"
            )
    except Exception as exc:
        logger.error("admin_update_settings_failed", error=str(exc))
        raise


async def admin_reset_settings(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    """Reset all admin_settings to their default values."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE admin_settings SET value = default_value, updated_at = now()"
            )
            return await conn.fetch(
                "SELECT key, value, default_value, updated_at FROM admin_settings ORDER BY key"
            )
    except Exception as exc:
        logger.error("admin_reset_settings_failed", error=str(exc))
        raise


# --- Audit Log ---
async def admin_list_audit_logs(
    pool: asyncpg.Pool,
    *,
    user_id: str | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[asyncpg.Record], int]:
    """Query audit_log with optional filters."""
    try:
        async with pool.acquire() as conn:
            conditions: list[str] = []
            params: list[object] = []
            idx = 1

            if user_id:
                conditions.append(f"user_id = ${idx}")
                params.append(user_id)
                idx += 1
            if action:
                conditions.append(f"action = ${idx}")
                params.append(action)
                idx += 1
            if date_from:
                conditions.append(f"created_at >= ${idx}")
                params.append(date_from)
                idx += 1
            if date_to:
                conditions.append(f"created_at <= ${idx}")
                params.append(date_to)
                idx += 1

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # Safe: where_clause built from hardcoded column names (RULE 02)
            count_query = f"SELECT count(*) FROM audit_log {where_clause}"  # noqa: S608
            total = await conn.fetchval(count_query, *params) or 0

            offset = (page - 1) * page_size
            params.extend([page_size, offset])
            data_query = (
                f"SELECT id::text, user_id, action, target_type, target_id, "  # noqa: S608
                f"ip_address, detail, created_at "
                f"FROM audit_log {where_clause} "
                f"ORDER BY created_at DESC "
                f"LIMIT ${idx} OFFSET ${idx + 1}"
            )
            rows = await conn.fetch(data_query, *params)
            return rows, total
    except Exception as exc:
        logger.error("admin_list_audit_logs_failed", error=str(exc))
        raise


# --- Analytics ---
async def admin_get_analytics_users(pool: asyncpg.Pool) -> dict:
    """Get user analytics: total, active, by plan."""
    try:
        async with pool.acquire() as conn:
            total = await conn.fetchval("SELECT count(*) FROM user_profile") or 0
            active = (
                await conn.fetchval("SELECT count(*) FROM user_profile WHERE is_active = true") or 0
            )
            by_plan = await conn.fetch(
                "SELECT plan, count(*) as count FROM user_profile GROUP BY plan"
            )
            return {
                "total": total,
                "active": active,
                "by_plan": {row["plan"]: row["count"] for row in by_plan},
            }
    except Exception as exc:
        logger.error("admin_get_analytics_users_failed", error=str(exc))
        raise


async def admin_get_analytics_revenue(pool: asyncpg.Pool) -> dict:
    """Get revenue analytics: active subscriptions by plan."""
    try:
        async with pool.acquire() as conn:
            active_subs = await conn.fetch(
                """
                SELECT plan, count(*) as count
                FROM subscription
                WHERE status = 'active'
                GROUP BY plan
                """
            )
            total_active = (
                await conn.fetchval("SELECT count(*) FROM subscription WHERE status = 'active'")
                or 0
            )
            return {
                "active_subscriptions": total_active,
                "by_plan": {row["plan"]: row["count"] for row in active_subs},
            }
    except Exception as exc:
        logger.error("admin_get_analytics_revenue_failed", error=str(exc))
        raise


async def admin_get_analytics_trends(pool: asyncpg.Pool) -> dict:
    """Get trend analytics: total news groups, today count."""
    try:
        async with pool.acquire() as conn:
            total = await conn.fetchval("SELECT count(*) FROM news_group") or 0
            today = (
                await conn.fetchval(
                    "SELECT count(*) FROM news_group WHERE created_at::date = CURRENT_DATE"
                )
                or 0
            )
            return {"total": total, "today": today}
    except Exception as exc:
        logger.error("admin_get_analytics_trends_failed", error=str(exc))
        raise


async def admin_get_analytics_api_usage(pool: asyncpg.Pool) -> dict:
    """Get API usage analytics."""
    try:
        async with pool.acquire() as conn:
            total_users_with_usage = (
                await conn.fetchval("SELECT count(DISTINCT user_id) FROM api_usage") or 0
            )
            return {"users_with_api_usage": total_users_with_usage}
    except Exception as exc:
        logger.error("admin_get_analytics_api_usage_failed", error=str(exc))
        raise
