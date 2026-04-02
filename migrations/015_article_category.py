"""015_article_category — Add category column to news_article, seed ai.config."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "015"
DESCRIPTION = "Add category column to news_article; backfill from feed_source; seed ai.config"

_AI_CONFIG_JSON = (
    '{"provider":"textrank","model":"textrank","api_key":"",'
    '"max_tokens":512,"temperature":0.0,"fallback_provider":"textrank"}'
)

STATEMENTS: list[str] = [
    # Add category column to partitioned parent table
    """
    ALTER TABLE news_article
        ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'general'
    """,
    # Backfill existing rows from feed_source.category via source name
    """
    UPDATE news_article na
    SET category = fs.category
    FROM feed_source fs
    WHERE na.source = fs.name
    """,
]

_AI_CONFIG_SEED = (
    "ai.config",
    _AI_CONFIG_JSON,
    _AI_CONFIG_JSON,
    "AI summarization provider config",
)


async def up(conn: asyncpg.Connection) -> None:
    """Apply migration 015."""
    try:
        for stmt in STATEMENTS:
            await conn.execute(stmt)
        logger.info("migration_015_ddl_complete")

        await conn.execute(
            """
            INSERT INTO admin_settings (key, value, default_value, description)
            VALUES ($1, to_jsonb($2::text), to_jsonb($3::text), $4)
            ON CONFLICT (key) DO NOTHING
            """,
            *_AI_CONFIG_SEED,
        )
        logger.info("migration_015_ai_config_seeded")
        logger.info("migration_015_complete")
    except Exception as exc:
        logger.error("migration_015_failed", error=str(exc))
        raise


async def down(conn: asyncpg.Connection) -> None:
    """Revert migration 015."""
    try:
        await conn.execute("DELETE FROM admin_settings WHERE key = 'ai.config'")
        await conn.execute("ALTER TABLE news_article DROP COLUMN IF EXISTS category")
        logger.info("migration_015_reverted")
    except Exception as exc:
        logger.error("migration_015_revert_failed", error=str(exc))
        raise
