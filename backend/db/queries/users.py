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
    """Fetch user_identity row by user_id + provider."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT id::text, user_id::text, provider, provider_uid, password_hash
                FROM user_identity
                WHERE user_id = $1::uuid AND provider = $2
                """,
                user_id,
                provider,
            )
    except Exception as exc:
        logger.error("get_identity_failed", error=str(exc))
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
