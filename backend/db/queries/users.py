"""DB query layer for user_profile and user_identity. (RULE 02: asyncpg $1,$2)"""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def get_user_by_email(pool: asyncpg.Pool, email: str) -> asyncpg.Record | None:
    """Fetch user_profile row by email."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT id::text, email, display_name, role, locale, plan, is_active
                FROM user_profile
                WHERE email = $1
                """,
                email,
            )
    except Exception as exc:
        logger.error("get_user_by_email_failed", error=str(exc))
        raise


async def get_user_by_id(pool: asyncpg.Pool, user_id: str) -> asyncpg.Record | None:
    """Fetch user_profile row by UUID string."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT id::text, email, display_name, role, locale, plan, is_active
                FROM user_profile
                WHERE id = $1::uuid
                """,
                user_id,
            )
    except Exception as exc:
        logger.error("get_user_by_id_failed", error=str(exc))
        raise


async def create_user(
    pool: asyncpg.Pool,
    *,
    email: str,
    display_name: str | None,
    role: str = "general",
    locale: str = "ko",
) -> asyncpg.Record:
    """Insert a new user_profile row and return it."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                """
                INSERT INTO user_profile (email, display_name, role, locale)
                VALUES ($1, $2, $3, $4)
                RETURNING id::text, email, display_name, role, locale, plan, is_active
                """,
                email,
                display_name,
                role,
                locale,
            )
    except Exception as exc:
        logger.error("create_user_failed", error=str(exc))
        raise


async def get_identity(
    pool: asyncpg.Pool,
    *,
    user_id: str,
    provider: str,
) -> asyncpg.Record | None:
    """Fetch user_identity row by user_id + provider (includes 2FA fields)."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT id::text, user_id::text, provider, provider_uid,
                       password_hash, two_fa_enabled, two_fa_secret
                FROM user_identity
                WHERE user_id = $1::uuid AND provider = $2
                """,
                user_id,
                provider,
            )
    except Exception as exc:
        logger.error("get_identity_failed", error=str(exc))
        raise


async def update_user(
    pool: asyncpg.Pool,
    user_id: str,
    **fields: object,
) -> asyncpg.Record | None:
    """Update user_profile fields dynamically. Returns the updated row.

    Only allows whitelisted columns to prevent injection (RULE 02).
    """
    allowed = {
        "display_name",
        "role",
        "locale",
        "category_weights",
        "plan",
        "is_active",
        "email_verified",
    }
    filtered = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not filtered:
        return await get_user_by_id(pool, user_id)

    set_clauses: list[str] = []
    params: list[object] = []
    for idx, (col, val) in enumerate(filtered.items(), start=1):
        set_clauses.append(f"{col} = ${idx + 1}")
        params.append(val)

    # Safe: set_clauses built from whitelisted column names only (RULE 02)
    query = (
        f"UPDATE user_profile SET {', '.join(set_clauses)}, updated_at = now() "  # noqa: S608
        f"WHERE id = $1::uuid "
        f"RETURNING id::text, email, display_name, role, locale, plan, is_active"
    )
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, user_id, *params)
    except Exception as exc:
        logger.error("update_user_failed", user_id=user_id, error=str(exc))
        raise


async def update_password_hash(
    pool: asyncpg.Pool,
    user_id: str,
    new_hash: str,
) -> None:
    """Update the password_hash on the email identity for a user."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE user_identity
                SET password_hash = $1
                WHERE user_id = $2::uuid AND provider = 'email'
                """,
                new_hash,
                user_id,
            )
    except Exception as exc:
        logger.error("update_password_hash_failed", user_id=user_id, error=str(exc))
        raise


async def update_2fa(
    pool: asyncpg.Pool,
    user_id: str,
    secret: str | None,
    enabled: bool,
) -> None:
    """Update 2FA secret and enabled flag on the email identity."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE user_identity
                SET two_fa_secret = $1, two_fa_enabled = $2
                WHERE user_id = $3::uuid AND provider = 'email'
                """,
                secret,
                enabled,
                user_id,
            )
    except Exception as exc:
        logger.error("update_2fa_failed", user_id=user_id, error=str(exc))
        raise


async def create_identity(
    pool: asyncpg.Pool,
    *,
    user_id: str,
    provider: str,
    provider_uid: str | None = None,
    password_hash: str | None = None,
) -> None:
    """Insert a user_identity row."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_identity (user_id, provider, provider_uid, password_hash)
                VALUES ($1::uuid, $2, $3, $4)
                ON CONFLICT (user_id, provider) DO NOTHING
                """,
                user_id,
                provider,
                provider_uid,
                password_hash,
            )
    except Exception as exc:
        logger.error("create_identity_failed", error=str(exc))
        raise


async def get_identity_by_provider_uid(
    pool: asyncpg.Pool,
    *,
    provider: str,
    provider_uid: str,
) -> asyncpg.Record | None:
    """Fetch user_identity by OAuth provider + uid (for login lookup)."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT ui.id::text, ui.user_id::text, ui.provider, ui.provider_uid
                FROM user_identity ui
                WHERE ui.provider = $1 AND ui.provider_uid = $2
                """,
                provider,
                provider_uid,
            )
    except Exception as exc:
        logger.error("get_identity_by_provider_uid_failed", error=str(exc))
        raise
