"""DB query layer for user settings (user_profile fields). (RULE 02: asyncpg $1,$2)"""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def get_user_settings(pool: asyncpg.Pool, *, user_id: str) -> asyncpg.Record | None:
    """Fetch settings-relevant fields from user_profile."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT id::text, display_name, role, locale, category_weights
                FROM user_profile
                WHERE id = $1::uuid
                """,
                user_id,
            )
    except Exception as exc:
        logger.error("get_user_settings_failed", user_id=user_id, error=str(exc))
        raise


async def update_user_settings(
    pool: asyncpg.Pool,
    *,
    user_id: str,
    display_name: str | None = None,
    role: str | None = None,
    locale: str | None = None,
    category_weights: dict | None = None,
) -> asyncpg.Record | None:
    """Update user settings. Only non-None fields are applied."""
    import json

    set_parts: list[str] = []
    params: list[object] = [user_id]
    idx = 2

    if display_name is not None:
        set_parts.append(f"display_name = ${idx}")
        params.append(display_name)
        idx += 1
    if role is not None:
        set_parts.append(f"role = ${idx}")
        params.append(role)
        idx += 1
    if locale is not None:
        set_parts.append(f"locale = ${idx}")
        params.append(locale)
        idx += 1
    if category_weights is not None:
        set_parts.append(f"category_weights = ${idx}::jsonb")
        params.append(json.dumps(category_weights))
        idx += 1

    if not set_parts:
        return await get_user_settings(pool, user_id=user_id)

    set_parts.append("updated_at = now()")

    # Safe: set_parts built from whitelisted column names only (RULE 02)
    query = (
        f"UPDATE user_profile SET {', '.join(set_parts)} "  # noqa: S608
        f"WHERE id = $1::uuid "
        f"RETURNING id::text, display_name, role, locale, category_weights"
    )
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *params)
    except Exception as exc:
        logger.error("update_user_settings_failed", user_id=user_id, error=str(exc))
        raise
