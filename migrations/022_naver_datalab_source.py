"""022_naver_datalab_source — Add naver_datalab to source_config + raw_data to sns_trend."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "022"
DESCRIPTION = "Add naver_datalab to source_config; add raw_data JSONB to sns_trend; add unique constraint"


async def up(conn: asyncpg.Connection) -> None:
    """Insert naver_datalab source config; add raw_data column and unique constraint to sns_trend."""

    # 1. Add raw_data JSONB column to sns_trend (idempotent)
    await conn.execute(
        """
        ALTER TABLE sns_trend
            ADD COLUMN IF NOT EXISTS raw_data JSONB
        """
    )
    logger.info("sns_trend_raw_data_column_added")

    # 2. Add unique constraint on (platform, keyword, locale) for ON CONFLICT support
    await conn.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_sns_trend_platform_keyword_locale'
            ) THEN
                ALTER TABLE sns_trend
                    ADD CONSTRAINT uq_sns_trend_platform_keyword_locale
                    UNIQUE (platform, keyword, locale);
            END IF;
        END $$;
        """
    )
    logger.info("sns_trend_unique_constraint_added")

    # 3. Insert naver_datalab source config
    await conn.execute(
        """
        INSERT INTO source_config (source_name, source_type, quota_limit)
        VALUES ($1, $2, $3)
        ON CONFLICT (source_name) DO NOTHING
        """,
        "naver_datalab",
        "api",
        1000,
    )
    logger.info("source_config_naver_datalab_inserted")


async def down(conn: asyncpg.Connection) -> None:
    """Remove naver_datalab source config; drop raw_data column and unique constraint."""

    await conn.execute(
        "DELETE FROM source_config WHERE source_name = $1",
        "naver_datalab",
    )
    logger.info("source_config_naver_datalab_deleted")

    await conn.execute(
        """
        ALTER TABLE sns_trend
            DROP CONSTRAINT IF EXISTS uq_sns_trend_platform_keyword_locale
        """
    )
    logger.info("sns_trend_unique_constraint_dropped")

    await conn.execute(
        """
        ALTER TABLE sns_trend
            DROP COLUMN IF EXISTS raw_data
        """
    )
    logger.info("sns_trend_raw_data_column_dropped")
