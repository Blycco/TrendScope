"""014_seed_source_config — source_config 시드 데이터 + admin_settings 초기화."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "014"
DESCRIPTION = "Seed source_config, backfill feed_source.source_config_id, seed admin_settings"

SOURCE_CONFIGS: list[dict[str, str | int]] = [
    {"source_name": "rss_ko", "source_type": "rss", "quota_limit": 5000},
    {"source_name": "rss_en", "source_type": "rss", "quota_limit": 3000},
    {"source_name": "dc_inside", "source_type": "scraper", "quota_limit": 1000},
    {"source_name": "fm_korea", "source_type": "scraper", "quota_limit": 1000},
    {"source_name": "reddit", "source_type": "api", "quota_limit": 2000},
    {"source_name": "nitter_rss", "source_type": "rss", "quota_limit": 500},
]

# feed_source.source_type → source_config.source_name 매핑
BACKFILL_RULES: list[tuple[str, str, str | None]] = [
    # (feed source_type, locale filter or None, source_config name)
    ("rss", "ko", "rss_ko"),
    ("rss", "en", "rss_en"),
    ("google_trends", None, "rss_ko"),
    ("community", None, "dc_inside"),  # DC + FM은 아래에서 분리
    ("reddit", None, "reddit"),
    ("nitter", None, "nitter_rss"),
]


async def up(conn: asyncpg.Connection) -> None:
    """Seed source_config, backfill feed_source, seed admin_settings."""

    # 1. source_config 시드
    for cfg in SOURCE_CONFIGS:
        await conn.execute(
            """
            INSERT INTO source_config (source_name, source_type, quota_limit)
            VALUES ($1, $2, $3)
            ON CONFLICT (source_name) DO NOTHING
            """,
            cfg["source_name"],
            cfg["source_type"],
            cfg["quota_limit"],
        )
    logger.info("source_config_seeded", count=len(SOURCE_CONFIGS))

    # 2. feed_source.source_config_id 소급 업데이트
    # RSS feeds — locale 기반 분류
    await conn.execute("""
        UPDATE feed_source SET source_config_id = sc.id
        FROM source_config sc
        WHERE feed_source.source_type = 'rss'
          AND feed_source.locale = 'ko'
          AND sc.source_name = 'rss_ko'
          AND feed_source.source_config_id IS NULL
    """)
    await conn.execute("""
        UPDATE feed_source SET source_config_id = sc.id
        FROM source_config sc
        WHERE feed_source.source_type = 'rss'
          AND feed_source.locale = 'en'
          AND sc.source_name = 'rss_en'
          AND feed_source.source_config_id IS NULL
    """)
    # Google Trends
    await conn.execute("""
        UPDATE feed_source SET source_config_id = sc.id
        FROM source_config sc
        WHERE feed_source.source_type = 'google_trends'
          AND sc.source_name = 'rss_ko'
          AND feed_source.source_config_id IS NULL
    """)
    # Community — DC Inside
    await conn.execute("""
        UPDATE feed_source SET source_config_id = sc.id
        FROM source_config sc
        WHERE feed_source.source_type = 'community'
          AND feed_source.name LIKE 'DC %'
          AND sc.source_name = 'dc_inside'
          AND feed_source.source_config_id IS NULL
    """)
    # Community — FM Korea
    await conn.execute("""
        UPDATE feed_source SET source_config_id = sc.id
        FROM source_config sc
        WHERE feed_source.source_type = 'community'
          AND feed_source.name LIKE 'FM Korea%'
          AND sc.source_name = 'fm_korea'
          AND feed_source.source_config_id IS NULL
    """)
    # Reddit
    await conn.execute("""
        UPDATE feed_source SET source_config_id = sc.id
        FROM source_config sc
        WHERE feed_source.source_type = 'reddit'
          AND sc.source_name = 'reddit'
          AND feed_source.source_config_id IS NULL
    """)
    # Nitter
    await conn.execute("""
        UPDATE feed_source SET source_config_id = sc.id
        FROM source_config sc
        WHERE feed_source.source_type = 'nitter'
          AND sc.source_name = 'nitter_rss'
          AND feed_source.source_config_id IS NULL
    """)
    logger.info("feed_source_config_ids_backfilled")

    # 3. admin_settings 시드
    from backend.db.seeds.admin_settings import SEEDS

    await conn.executemany(
        """
        INSERT INTO admin_settings (key, value, default_value, description)
        VALUES ($1, to_jsonb($2::text), to_jsonb($3::text), $4)
        ON CONFLICT (key) DO NOTHING
        """,
        SEEDS,
    )
    logger.info("admin_settings_seeded", count=len(SEEDS))


async def down(conn: asyncpg.Connection) -> None:
    """Remove seeded source_config rows and clear backfilled IDs."""
    await conn.execute("UPDATE feed_source SET source_config_id = NULL")
    await conn.execute("DELETE FROM source_config")
    await conn.execute("DELETE FROM admin_settings")
    logger.info("seed_source_config_reverted")
