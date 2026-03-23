"""Community crawler — DC Inside RSS + FM Korea RSS/crawl."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

import asyncpg
import feedparser
import httpx
import structlog
from bs4 import BeautifulSoup

from backend.common.metrics import CRAWLER_REQUESTS
from backend.crawler.quota_guard import check_quota, increment_quota
from backend.crawler.sources.robots import is_allowed
from backend.crawler.sources.rss_feeds import COMMUNITY_FEEDS, FeedSource

logger = structlog.get_logger(__name__)

_HTTP_TIMEOUT = 15.0


def _url_hash(url: str) -> str:
    """SHA-256[:16] of URL for dedup."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _content_fp(title: str, body: str) -> str:
    """SHA-256(title+body[:200])[:16] for content dedup."""
    raw = f"{title}{body[:200]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def crawl_dc_inside(db_pool: asyncpg.Pool) -> list[dict[str, Any]]:
    """Crawl DC Inside gallery feeds via RSS."""
    try:
        if not await check_quota("dc_inside", db_pool):
            return []

        dc_feeds = [f for f in COMMUNITY_FEEDS if f["name"].startswith("DC ")]
        articles: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            headers={"User-Agent": "TrendScopeBot/1.0"},
        ) as client:
            for feed in dc_feeds:
                try:
                    new_items = await _crawl_rss_feed(client, feed, db_pool)
                    articles.extend(new_items)
                    await increment_quota("dc_inside", db_pool)
                except Exception as exc:
                    logger.warning("dc_feed_error", feed=feed["name"], error=str(exc))
                    continue

        CRAWLER_REQUESTS.labels(source="dc_inside", result="success").inc()
        logger.info("dc_inside_crawl_complete", total=len(articles))
        return articles
    except Exception as exc:
        CRAWLER_REQUESTS.labels(source="dc_inside", result="failure").inc()
        logger.error("dc_inside_crawl_failed", error=str(exc))
        return []


async def crawl_fm_korea(db_pool: asyncpg.Pool) -> list[dict[str, Any]]:
    """Crawl FM Korea feeds via RSS, with HTML scrape fallback."""
    try:
        if not await check_quota("fm_korea", db_pool):
            return []

        fm_feeds = [f for f in COMMUNITY_FEEDS if f["name"].startswith("FM Korea")]
        articles: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            headers={"User-Agent": "TrendScopeBot/1.0"},
            follow_redirects=True,
        ) as client:
            for feed in fm_feeds:
                try:
                    new_items = await _crawl_rss_feed(client, feed, db_pool)
                    if not new_items:
                        new_items = await _crawl_fm_html(client, feed, db_pool)
                    articles.extend(new_items)
                    await increment_quota("fm_korea", db_pool)
                except Exception as exc:
                    logger.warning("fm_feed_error", feed=feed["name"], error=str(exc))
                    continue

        CRAWLER_REQUESTS.labels(source="fm_korea", result="success").inc()
        logger.info("fm_korea_crawl_complete", total=len(articles))
        return articles
    except Exception as exc:
        CRAWLER_REQUESTS.labels(source="fm_korea", result="failure").inc()
        logger.error("fm_korea_crawl_failed", error=str(exc))
        return []


async def _crawl_rss_feed(
    client: httpx.AsyncClient,
    feed: FeedSource,
    db_pool: asyncpg.Pool,
) -> list[dict[str, Any]]:
    """Generic RSS crawl for community feeds."""
    resp = await client.get(feed["url"])
    if resp.status_code != 200:
        return []

    parsed = feedparser.parse(resp.text)
    articles: list[dict[str, Any]] = []

    for entry in parsed.entries:
        try:
            url = entry.get("link", "")
            title = entry.get("title", "").strip()
            if not url or not title:
                continue

            uhash = _url_hash(url)

            existing = await db_pool.fetchval(
                "SELECT 1 FROM news_article WHERE url_hash = $1 LIMIT 1",
                uhash,
            )
            if existing:
                continue

            body = entry.get("summary", "").strip()
            cfp = _content_fp(title, body)
            published = _parse_time(entry)

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
                entry.get("author", ""),
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
                    "publish_time": published,
                    "locale": feed["locale"],
                    "category": feed["category"],
                }
            )
        except Exception as exc:
            logger.warning("community_entry_error", title=entry.get("title", "?"), error=str(exc))
            continue

    return articles


async def _crawl_fm_html(
    client: httpx.AsyncClient,
    feed: FeedSource,
    db_pool: asyncpg.Pool,
) -> list[dict[str, Any]]:
    """HTML scrape fallback for FM Korea when RSS is incomplete."""
    try:
        base_url = feed["url"].split("?")[0]
        page_url = base_url.replace("/index.php", "")

        if not await is_allowed(page_url):
            logger.info("fm_html_robots_blocked", url=page_url)
            return []

        resp = await client.get(page_url)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        articles: list[dict[str, Any]] = []

        for link_tag in soup.select("a.hotdeal_var8"):
            try:
                title = link_tag.get_text(strip=True)
                href = link_tag.get("href", "")
                if not title or not href:
                    continue

                if href.startswith("/"):
                    href = f"https://www.fmkorea.com{href}"

                uhash = _url_hash(href)
                existing = await db_pool.fetchval(
                    "SELECT 1 FROM news_article WHERE url_hash = $1 LIMIT 1",
                    uhash,
                )
                if existing:
                    continue

                cfp = _content_fp(title, "")

                await db_pool.execute(
                    "INSERT INTO news_article "
                    "(url, url_hash, content_fp, title, body, source, author, publish_time, locale)"
                    " "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
                    "ON CONFLICT DO NOTHING",
                    href,
                    uhash,
                    cfp,
                    title,
                    "",
                    feed["name"],
                    "",
                    datetime.now(tz=timezone.utc),
                    feed["locale"],
                )

                articles.append(
                    {
                        "url": href,
                        "url_hash": uhash,
                        "content_fp": cfp,
                        "title": title,
                        "body": "",
                        "source": feed["name"],
                        "publish_time": datetime.now(tz=timezone.utc),
                        "locale": feed["locale"],
                        "category": feed["category"],
                    }
                )
            except Exception as exc:
                logger.warning("fm_html_entry_error", error=str(exc))
                continue

        return articles
    except Exception as exc:
        logger.warning("fm_html_crawl_failed", error=str(exc))
        return []


def _parse_time(entry: Any) -> datetime:  # noqa: ANN401
    """Parse time from feed entry, fallback to now()."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        from time import mktime

        return datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        from time import mktime

        return datetime.fromtimestamp(mktime(entry.updated_parsed), tz=timezone.utc)
    return datetime.now(tz=timezone.utc)


async def crawl_all(db_pool: asyncpg.Pool) -> list[dict[str, Any]]:
    """Crawl all community sources."""
    all_articles: list[dict[str, Any]] = []

    dc_articles = await crawl_dc_inside(db_pool)
    all_articles.extend(dc_articles)

    fm_articles = await crawl_fm_korea(db_pool)
    all_articles.extend(fm_articles)

    logger.info("community_crawl_all_complete", total=len(all_articles))
    return all_articles
