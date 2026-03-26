"""012_seed_feed_sources — 기존 하드코딩 피드를 feed_source 테이블에 시드."""

from __future__ import annotations

import json

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

VERSION = "012"
DESCRIPTION = "Seed feed_source table from hardcoded rss_feeds.py constants"


async def _lookup_source_config_id(
    conn: asyncpg.Connection, source_name: str
) -> str | None:
    """source_config 테이블에서 source_name으로 UUID 조회."""
    row = await conn.fetchrow(
        "SELECT id::text FROM source_config WHERE source_name = $1",
        source_name,
    )
    return row["id"] if row else None


async def _insert_feeds(
    conn: asyncpg.Connection,
    feeds: list[dict[str, str]],
    source_type: str,
    source_config_id: str | None,
    config_extra: dict[str, str] | None = None,
) -> int:
    """feed_source에 피드 목록 INSERT (ON CONFLICT 무시)."""
    count = 0
    for feed in feeds:
        cfg = json.dumps(config_extra or {})
        result = await conn.execute(
            """
            INSERT INTO feed_source (
                source_config_id, source_type, name, url, category, locale, config
            ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb)
            ON CONFLICT (url) DO NOTHING
            """,
            source_config_id,
            source_type,
            feed["name"],
            feed["url"],
            feed["category"],
            feed["locale"],
            cfg,
        )
        if result == "INSERT 0 1":
            count += 1
    return count


async def up(conn: asyncpg.Connection) -> None:
    """Seed feed_source from rss_feeds.py constants."""
    from backend.crawler.sources.rss_feeds import (
        COMMUNITY_FEEDS,
        GLOBAL_NEWS_FEEDS,
        GOOGLE_TRENDS_FEEDS,
        KR_NEWS_FEEDS,
        NITTER_INSTANCES,
        REDDIT_SUBREDDITS,
    )

    # source_config ID lookup
    rss_ko_id = await _lookup_source_config_id(conn, "rss_ko")
    rss_en_id = await _lookup_source_config_id(conn, "rss_en")
    dc_id = await _lookup_source_config_id(conn, "dc_inside")
    fm_id = await _lookup_source_config_id(conn, "fm_korea")
    reddit_id = await _lookup_source_config_id(conn, "reddit")
    nitter_id = await _lookup_source_config_id(conn, "nitter_rss")

    total = 0

    # Korean news RSS
    total += await _insert_feeds(conn, KR_NEWS_FEEDS, "rss", rss_ko_id)
    logger.info("seed_kr_news", count=len(KR_NEWS_FEEDS))

    # Global news RSS
    total += await _insert_feeds(conn, GLOBAL_NEWS_FEEDS, "rss", rss_en_id)
    logger.info("seed_global_news", count=len(GLOBAL_NEWS_FEEDS))

    # Google Trends RSS
    total += await _insert_feeds(conn, GOOGLE_TRENDS_FEEDS, "google_trends", rss_ko_id)
    logger.info("seed_google_trends", count=len(GOOGLE_TRENDS_FEEDS))

    # Community — DC Inside
    dc_feeds = [f for f in COMMUNITY_FEEDS if f["name"].startswith("DC ")]
    total += await _insert_feeds(conn, dc_feeds, "community", dc_id)
    logger.info("seed_dc_inside", count=len(dc_feeds))

    # Community — FM Korea
    fm_feeds = [f for f in COMMUNITY_FEEDS if f["name"].startswith("FM Korea")]
    total += await _insert_feeds(conn, fm_feeds, "community", fm_id)
    logger.info("seed_fm_korea", count=len(fm_feeds))

    # Reddit subreddits
    reddit_feeds: list[dict[str, str]] = []
    subreddit_categories = {
        "worldnews": "general",
        "technology": "it",
        "korea": "general",
        "kpop": "entertainment",
        "science": "it",
        "news": "general",
        "business": "economy",
        "stocks": "economy",
        "cryptocurrency": "economy",
        "gaming": "entertainment",
        "entertainment": "entertainment",
        "sports": "sports",
        "movies": "entertainment",
        "television": "entertainment",
        "music": "entertainment",
        "artificial": "it",
        "machinelearning": "it",
        "programming": "it",
        "startups": "economy",
    }
    for sub in REDDIT_SUBREDDITS:
        reddit_feeds.append({
            "name": f"r/{sub}",
            "url": f"https://www.reddit.com/r/{sub}/hot.json",
            "category": subreddit_categories.get(sub, "general"),
            "locale": "en",
        })
    for feed in reddit_feeds:
        cfg = json.dumps({"subreddit": feed["name"].removeprefix("r/")})
        result = await conn.execute(
            """
            INSERT INTO feed_source (
                source_config_id, source_type, name, url, category, locale, config
            ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb)
            ON CONFLICT (url) DO NOTHING
            """,
            reddit_id,
            "reddit",
            feed["name"],
            feed["url"],
            feed["category"],
            feed["locale"],
            cfg,
        )
        if result == "INSERT 0 1":
            total += 1
    logger.info("seed_reddit", count=len(REDDIT_SUBREDDITS))

    # Nitter instances
    for instance in NITTER_INSTANCES:
        result = await conn.execute(
            """
            INSERT INTO feed_source (
                source_config_id, source_type, name, url, category, locale, config
            ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb)
            ON CONFLICT (url) DO NOTHING
            """,
            nitter_id,
            "nitter",
            f"Nitter ({instance})",
            f"https://{instance}/search/rss?f=tweets&q=trending",
            "general",
            "en",
            json.dumps({"instance": instance}),
        )
        if result == "INSERT 0 1":
            total += 1
    logger.info("seed_nitter", count=len(NITTER_INSTANCES))

    logger.info("seed_feed_sources_complete", total_inserted=total)


async def down(conn: asyncpg.Connection) -> None:
    """Remove all seeded feed_source rows."""
    await conn.execute("DELETE FROM feed_source")
    logger.info("feed_source_seeds_removed")
