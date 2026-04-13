"""026_add_is_hidden — news_group에 is_hidden 컬럼 추가 (수동 트렌드 숨김용)."""

from __future__ import annotations

import asyncpg

VERSION = "026"
DESCRIPTION = "Add is_hidden column to news_group for manual trend suppression"


async def up(conn: asyncpg.Connection) -> None:
    await conn.execute("""
        ALTER TABLE news_group
            ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT FALSE
    """)
