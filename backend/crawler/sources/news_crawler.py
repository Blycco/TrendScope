"""Async RSS news crawler with ETag/If-Modified-Since support."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import asyncpg
import feedparser
import httpx
import structlog
from bs4 import BeautifulSoup

from backend.common.metrics import CRAWLER_REQUESTS
from backend.crawler.quota_guard import check_quota, increment_quota
from backend.crawler.sources.extractor import _MIN_BODY_LENGTH, extract_body
from backend.crawler.sources.rss_feeds import FeedSource
from backend.db.queries.feed_sources import get_feed_sources_for_crawl, update_feed_health
from backend.processor.shared.cache_manager import get_cached, set_cached
from backend.processor.shared.dedupe_filter import (
    compute_content_fingerprint as _content_fp,
)
from backend.processor.shared.dedupe_filter import (
    compute_url_hash as _url_hash,
)

logger = structlog.get_logger(__name__)

_ETAG_CACHE_TTL = 86400  # 24 hours
_HTTP_TIMEOUT = 20.0


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

        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "TrendScopeBot/1.0"},
        ) as client:
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
                client=client,
                extract_bodies=extract_bodies,
            )
        CRAWLER_REQUESTS.labels(source=feed["name"], result="success").inc()
        logger.info(
            "feed_crawled",
            feed=feed["name"],
            new_articles=len(articles),
            total_entries=len(parsed.entries),
        )
        return articles

    except Exception as exc:
        CRAWLER_REQUESTS.labels(source=feed.get("name", "unknown"), result="failure").inc()
        logger.error("feed_crawl_error", feed=feed.get("name", "?"), error=str(exc))
        return []


async def _process_entries(
    entries: list[Any],
    feed: FeedSource,
    db_pool: asyncpg.Pool,
    *,
    client: httpx.AsyncClient,
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
                summary_raw = entry.get("summary", "")
                body = _sanitize_summary(summary_raw)
                if len(body) < _MIN_BODY_LENGTH:
                    body = await extract_body(url, client=client)

            cfp = _content_fp(title, body)

            published = _parse_published(entry)
            author = entry.get("author", "")
            category = await _infer_category(title, body, feed["category"], db_pool)

            await db_pool.execute(
                "INSERT INTO news_article "
                "(url, url_hash, content_fp, title, body, source, "
                "author, publish_time, locale, category) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) "
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
                category,
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
                    "category": category,
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


async def _infer_category(
    title: str,
    body: str,
    feed_category: str,
    db_pool: asyncpg.Pool,
) -> str:
    """키워드 매칭 기반 카테고리 재분류.

    category_keyword 테이블(is_active=TRUE)에서 카테고리별 키워드를 로드해
    제목 + 본문 앞 200자에서 weight 합산 후, 최고 합산 카테고리를 반환.
    합계 < 3.0 이면 feed_category 그대로 반환.
    """
    try:
        from backend.processor.shared.config_loader import get_category_keywords

        category_map = await get_category_keywords(db_pool)
        if not category_map:
            return feed_category

        text = (title + " " + body[:200]).lower()
        scores: dict[str, float] = {}
        for cat, kw_list in category_map.items():
            total = sum(weight for kw, weight in kw_list if kw.lower() in text)
            if total > 0:
                scores[cat] = total

        if not scores:
            return feed_category

        best_cat, best_score = max(scores.items(), key=lambda x: x[1])
        return best_cat if best_score >= 3.0 else feed_category

    except Exception as exc:
        logger.warning("infer_category_failed", error=str(exc))
        return feed_category


def _sanitize_summary(raw: str) -> str:
    """Strip HTML tags from RSS summary, return plain text."""
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "lxml")
    return soup.get_text(separator="\n", strip=True)


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
    """Crawl all configured news feeds from DB and return all new articles."""
    all_articles: list[dict[str, Any]] = []
    feed_rows = await get_feed_sources_for_crawl(db_pool, "rss")

    for row in feed_rows:
        feed: FeedSource = {
            "url": row["url"],
            "name": row["name"],
            "category": row["category"],
            "locale": row["locale"],
        }
        feed_id = row["id"]
        t0 = time.monotonic()
        try:
            articles = await crawl_feed(feed, db_pool)
            elapsed_ms = (time.monotonic() - t0) * 1000
            await update_feed_health(db_pool, feed_id, success=True, latency_ms=elapsed_ms)
            all_articles.extend(articles)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - t0) * 1000
            await update_feed_health(
                db_pool, feed_id, success=False, latency_ms=elapsed_ms, error=str(exc)
            )
            logger.warning("feed_crawl_health_error", feed=feed["name"], error=str(exc))

    logger.info("crawl_all_complete", total_new=len(all_articles))
    return all_articles
