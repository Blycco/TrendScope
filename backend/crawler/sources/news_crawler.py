"""Async RSS news crawler with ETag/If-Modified-Since support."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

import asyncpg
import feedparser
import httpx
import structlog

from backend.crawler.quota_guard import check_quota, increment_quota
from backend.crawler.sources.extractor import extract_body
from backend.crawler.sources.rss_feeds import ALL_NEWS_FEEDS, FeedSource
from backend.processor.shared.cache_manager import get_cached, set_cached

logger = structlog.get_logger(__name__)

_ETAG_CACHE_TTL = 86400  # 24 hours
_HTTP_TIMEOUT = 20.0


def _url_hash(url: str) -> str:
    """SHA-256[:16] of URL for dedup."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _content_fp(title: str, body: str) -> str:
    """SHA-256(title+body[:200])[:16] for content dedup."""
    raw = f"{title}{body[:200]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def crawl_feed(
    feed: FeedSource,
    db_pool: asyncpg.Pool,
    *,
    extract_bodies: bool = True,
) -> list[dict[str, Any]]:
    """Crawl a single RSS feed and return new article dicts.

    Uses ETag / If-Modified-Since headers for 304 skip.
    Inserts new articles into news_article table.
    """
    try:
        source_name = f"rss_{feed['locale']}"
        if not await check_quota(source_name, db_pool):
            return []

        feed_url = feed["url"]
        cache_key_etag = f"etag:{feed_url}"
        cache_key_modified = f"modified:{feed_url}"

        headers: dict[str, str] = {"User-Agent": "TrendScopeBot/1.0"}

        cached_etag = await get_cached(cache_key_etag)
        if cached_etag:
            headers["If-None-Match"] = (
                cached_etag.decode("utf-8") if isinstance(cached_etag, bytes) else cached_etag
            )

        cached_modified = await get_cached(cache_key_modified)
        if cached_modified:
            headers["If-Modified-Since"] = (
                cached_modified.decode("utf-8")
                if isinstance(cached_modified, bytes)
                else cached_modified
            )

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(feed_url, headers=headers)

        if resp.status_code == 304:
            logger.debug("feed_not_modified", feed=feed["name"])
            return []

        if resp.status_code != 200:
            logger.warning("feed_fetch_failed", feed=feed["name"], status=resp.status_code)
            return []

        if etag := resp.headers.get("ETag"):
            await set_cached(cache_key_etag, etag.encode("utf-8"), _ETAG_CACHE_TTL)
        if modified := resp.headers.get("Last-Modified"):
            await set_cached(cache_key_modified, modified.encode("utf-8"), _ETAG_CACHE_TTL)

        await increment_quota(source_name, db_pool)

        parsed = feedparser.parse(resp.text)
        articles = await _process_entries(
            parsed.entries,
            feed,
            db_pool,
            extract_bodies=extract_bodies,
        )
        logger.info(
            "feed_crawled",
            feed=feed["name"],
            new_articles=len(articles),
            total_entries=len(parsed.entries),
        )
        return articles

    except Exception as exc:
        logger.error("feed_crawl_error", feed=feed.get("name", "?"), error=str(exc))
        return []


async def _process_entries(
    entries: list[Any],
    feed: FeedSource,
    db_pool: asyncpg.Pool,
    *,
    extract_bodies: bool,
) -> list[dict[str, Any]]:
    """Process feed entries: dedup, extract body, insert into DB."""
    articles: list[dict[str, Any]] = []

    for entry in entries:
        try:
            url = entry.get("link", "")
            if not url:
                continue

            title = entry.get("title", "").strip()
            if not title:
                continue

            uhash = _url_hash(url)

            existing = await db_pool.fetchval(
                "SELECT 1 FROM news_article WHERE url_hash = $1 LIMIT 1",
                uhash,
            )
            if existing:
                continue

            body = ""
            if extract_bodies:
                summary = entry.get("summary", "")
                body = await extract_body(url, html=None) if not summary else summary

            cfp = _content_fp(title, body)

            published = _parse_published(entry)
            author = entry.get("author", "")

            await db_pool.execute(
                "INSERT INTO news_article "
                "(url, url_hash, content_fp, title, body, source, author, publish_time, locale) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
                "ON CONFLICT DO NOTHING",
                url,
                uhash,
                cfp,
                title,
                body,
                feed["name"],
                author,
                published,
                feed["locale"],
            )

            articles.append(
                {
                    "url": url,
                    "url_hash": uhash,
                    "content_fp": cfp,
                    "title": title,
                    "body": body,
                    "source": feed["name"],
                    "author": author,
                    "publish_time": published,
                    "locale": feed["locale"],
                    "category": feed["category"],
                }
            )

        except Exception as exc:
            logger.warning(
                "entry_process_error",
                feed=feed["name"],
                entry_title=entry.get("title", "?"),
                error=str(exc),
            )
            continue

    return articles


def _parse_published(entry: Any) -> datetime:  # noqa: ANN401
    """Parse published date from feed entry, fallback to now()."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        from time import mktime

        return datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        from time import mktime

        return datetime.fromtimestamp(mktime(entry.updated_parsed), tz=timezone.utc)
    return datetime.now(tz=timezone.utc)


async def crawl_all(db_pool: asyncpg.Pool) -> list[dict[str, Any]]:
    """Crawl all configured news feeds and return all new articles."""
    all_articles: list[dict[str, Any]] = []
    for feed in ALL_NEWS_FEEDS:
        articles = await crawl_feed(feed, db_pool)
        all_articles.extend(articles)
    logger.info("crawl_all_complete", total_new=len(all_articles))
    return all_articles
