"""023_config_tables — stopword, filter_keyword, category_keyword 테이블 생성."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "023"
DESCRIPTION = "Create stopword, filter_keyword, category_keyword tables"


async def up(conn: asyncpg.Connection) -> None:
    """Create config management tables."""
    # 불용어 관리
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS stopword (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            word       TEXT NOT NULL,
            locale     TEXT NOT NULL DEFAULT 'ko',
            is_active  BOOLEAN NOT NULL DEFAULT TRUE,
            source     TEXT NOT NULL DEFAULT 'system',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    await conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_stopword_word_locale
        ON stopword (word, locale)
    """)

    # 필터 키워드 (스팸/비트렌드 통합)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS filter_keyword (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            keyword    TEXT NOT NULL,
            category   TEXT NOT NULL,
            source     TEXT NOT NULL DEFAULT 'system',
            is_active  BOOLEAN NOT NULL DEFAULT TRUE,
            confidence FLOAT NOT NULL DEFAULT 1.0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    await conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_filter_keyword
        ON filter_keyword (keyword)
    """)

    # 카테고리 분류 키워드
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS category_keyword (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            keyword    TEXT NOT NULL,
            category   TEXT NOT NULL,
            weight     FLOAT NOT NULL DEFAULT 1.0,
            locale     TEXT NOT NULL DEFAULT 'ko',
            is_active  BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    await conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_category_keyword
        ON category_keyword (keyword, category)
    """)

    logger.info("migration_023_complete")


async def down(conn: asyncpg.Connection) -> None:
    """Drop config tables."""
    await conn.execute("DROP TABLE IF EXISTS category_keyword CASCADE")
    await conn.execute("DROP TABLE IF EXISTS filter_keyword CASCADE")
    await conn.execute("DROP TABLE IF EXISTS stopword CASCADE")
    logger.info("migration_023_reverted")
