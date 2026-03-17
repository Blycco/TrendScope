"""SNS crawler — Reddit JSON API + Nitter RSS + YouTube Data API v3."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import asyncpg
import feedparser
import httpx
import structlog

from backend.crawler.quota_guard import check_quota, increment_quota
from backend.crawler.sources.rss_feeds import NITTER_INSTANCES, REDDIT_SUBREDDITS

logger = structlog.get_logger(__name__)

_HTTP_TIMEOUT = 15.0


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------


async def crawl_reddit(
    db_pool: asyncpg.Pool,
    subreddits: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch hot posts from Reddit JSON API for each subreddit."""
    try:
        if not await check_quota("reddit", db_pool):
            return []

        subs = subreddits or REDDIT_SUBREDDITS
        results: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            headers={"User-Agent": "TrendScopeBot/1.0 (trend aggregation)"},
        ) as client:
            for sub in subs:
                try:
                    posts = await _fetch_subreddit(client, sub, db_pool)
                    results.extend(posts)
                except Exception as exc:
                    logger.warning("reddit_sub_error", subreddit=sub, error=str(exc))
                    continue

        logger.info("reddit_crawl_complete", total=len(results))
        return results
    except Exception as exc:
        logger.error("reddit_crawl_failed", error=str(exc))
        return []


async def _fetch_subreddit(
    client: httpx.AsyncClient,
    subreddit: str,
    db_pool: asyncpg.Pool,
) -> list[dict[str, Any]]:
    """Fetch hot posts from a single subreddit."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json"
    resp = await client.get(url, params={"limit": 25})
    resp.raise_for_status()
    await increment_quota("reddit", db_pool)

    data = resp.json()
    children = data.get("data", {}).get("children", [])
    results: list[dict[str, Any]] = []

    for child in children:
        post = child.get("data", {})
        if not post.get("title"):
            continue

        created_utc = post.get("created_utc", 0)
        snapshot_at = (
            datetime.fromtimestamp(created_utc, tz=timezone.utc)
            if created_utc
            else datetime.now(tz=timezone.utc)
        )

        record = {
            "platform": "reddit",
            "keyword": post["title"],
            "locale": "en",
            "category": _reddit_category(subreddit),
            "score": float(post.get("score", 0)),
            "burst_z": 0.0,
            "sentiment_badge": "neutral",
            "snapshot_at": snapshot_at,
            "meta": {
                "subreddit": subreddit,
                "permalink": post.get("permalink", ""),
                "num_comments": post.get("num_comments", 0),
                "ups": post.get("ups", 0),
            },
        }
        results.append(record)

    return results


def _reddit_category(subreddit: str) -> str:
    """Map subreddit to TrendScope category."""
    mapping: dict[str, str] = {
        "worldnews": "general",
        "news": "general",
        "korea": "general",
        "technology": "it",
        "programming": "it",
        "machinelearning": "it",
        "artificial": "it",
        "science": "it",
        "business": "economy",
        "stocks": "economy",
        "cryptocurrency": "economy",
        "startups": "economy",
        "gaming": "entertainment",
        "entertainment": "entertainment",
        "movies": "entertainment",
        "television": "entertainment",
        "music": "entertainment",
        "kpop": "entertainment",
        "sports": "sports",
    }
    return mapping.get(subreddit, "general")


# ---------------------------------------------------------------------------
# Nitter (X / Twitter RSS fallback)
# ---------------------------------------------------------------------------


async def crawl_nitter(db_pool: asyncpg.Pool) -> list[dict[str, Any]]:
    """Fetch trending search terms via Nitter RSS instances."""
    try:
        if not await check_quota("nitter_rss", db_pool):
            return []

        results: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            for instance in NITTER_INSTANCES:
                try:
                    feed_url = f"https://{instance}/search/rss?f=tweets&q=trending"
                    resp = await client.get(feed_url)
                    if resp.status_code != 200:
                        continue

                    parsed = feedparser.parse(resp.text)
                    await increment_quota("nitter_rss", db_pool)

                    for entry in parsed.entries:
                        title = entry.get("title", "").strip()
                        if not title:
                            continue
                        results.append(
                            {
                                "platform": "twitter",
                                "keyword": title,
                                "locale": "en",
                                "category": "general",
                                "score": 0.0,
                                "burst_z": 0.0,
                                "sentiment_badge": "neutral",
                                "snapshot_at": datetime.now(tz=timezone.utc),
                                "meta": {
                                    "instance": instance,
                                    "link": entry.get("link", ""),
                                },
                            }
                        )
                    break  # success on one instance is enough
                except Exception as exc:
                    logger.debug("nitter_instance_error", instance=instance, error=str(exc))
                    continue

        logger.info("nitter_crawl_complete", total=len(results))
        return results
    except Exception as exc:
        logger.error("nitter_crawl_failed", error=str(exc))
        return []


# ---------------------------------------------------------------------------
# YouTube Data API v3
# ---------------------------------------------------------------------------


async def crawl_youtube(db_pool: asyncpg.Pool) -> list[dict[str, Any]]:
    """Fetch trending videos from YouTube Data API v3."""
    try:
        api_key = os.environ.get("YOUTUBE_API_KEY")
        if not api_key:
            raise RuntimeError("YOUTUBE_API_KEY environment variable is not set")

        if not await check_quota("youtube", db_pool):
            return []

        results: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            for region, locale in [("KR", "ko"), ("US", "en")]:
                try:
                    videos = await _fetch_youtube_trending(client, api_key, region, locale, db_pool)
                    results.extend(videos)
                except Exception as exc:
                    logger.warning("youtube_region_error", region=region, error=str(exc))
                    continue

        logger.info("youtube_crawl_complete", total=len(results))
        return results
    except Exception as exc:
        logger.error("youtube_crawl_failed", error=str(exc))
        return []


async def _fetch_youtube_trending(
    client: httpx.AsyncClient,
    api_key: str,
    region_code: str,
    locale: str,
    db_pool: asyncpg.Pool,
) -> list[dict[str, Any]]:
    """Fetch trending videos for a specific region."""
    resp = await client.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": region_code,
            "maxResults": 25,
            "key": api_key,
        },
    )
    resp.raise_for_status()
    await increment_quota("youtube", db_pool)

    data = resp.json()
    results: list[dict[str, Any]] = []

    for item in data.get("items", []):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})

        results.append(
            {
                "platform": "youtube",
                "keyword": snippet.get("title", ""),
                "locale": locale,
                "category": "entertainment",
                "score": float(stats.get("viewCount", 0)),
                "burst_z": 0.0,
                "sentiment_badge": "neutral",
                "snapshot_at": datetime.now(tz=timezone.utc),
                "meta": {
                    "video_id": item.get("id", ""),
                    "channel": snippet.get("channelTitle", ""),
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "comment_count": int(stats.get("commentCount", 0)),
                },
            }
        )

    return results


# ---------------------------------------------------------------------------
# Aggregated collect
# ---------------------------------------------------------------------------


async def collect_all(db_pool: asyncpg.Pool) -> list[dict[str, Any]]:
    """Collect from all SNS sources and insert into sns_trend table."""
    all_items: list[dict[str, Any]] = []

    reddit_items = await crawl_reddit(db_pool)
    all_items.extend(reddit_items)

    nitter_items = await crawl_nitter(db_pool)
    all_items.extend(nitter_items)

    youtube_items = await crawl_youtube(db_pool)
    all_items.extend(youtube_items)

    saved = await _save_sns_trends(all_items, db_pool)
    logger.info("sns_collect_all_complete", collected=len(all_items), saved=saved)
    return all_items


async def _save_sns_trends(items: list[dict[str, Any]], db_pool: asyncpg.Pool) -> int:
    """Insert SNS trend items into sns_trend table."""
    saved = 0
    for item in items:
        try:
            await db_pool.execute(
                "INSERT INTO sns_trend "
                "(platform, keyword, locale, category, score,"
                " burst_z, sentiment_badge, snapshot_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
                item["platform"],
                item["keyword"][:500],
                item["locale"],
                item.get("category", "general"),
                item["score"],
                item["burst_z"],
                item.get("sentiment_badge", "neutral"),
                item["snapshot_at"],
            )
            saved += 1
        except Exception as exc:
            logger.warning("sns_trend_save_error", keyword=item.get("keyword", "?"), error=str(exc))
            continue
    return saved
