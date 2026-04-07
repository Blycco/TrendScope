"""Keyword-based search crawlers for burst job — Google News RSS + Reddit."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

import asyncpg
import feedparser
import httpx
import structlog

from backend.processor.shared.dedupe_filter import (
    compute_content_fingerprint as _content_fp,
)
from backend.processor.shared.dedupe_filter import (
    compute_url_hash as _url_hash,
)

logger = structlog.get_logger(__name__)

_HTTP_TIMEOUT = 15.0
_USER_AGENT = "TrendScopeBot/1.0 (burst crawl)"

_LOCALE_MAP: dict[str, dict[str, str]] = {
    "ko": {"hl": "ko", "gl": "KR", "ceid": "KR:ko"},
    "en": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
}


async def search_google_news_rss(
    keywords: list[str],
    locale: str,
    db_pool: asyncpg.Pool,
) -> list[dict[str, Any]]:
    """Search Google News RSS for articles matching keywords.

    Constructs URL: https://news.google.com/rss/search?q={query}&hl=...&gl=...&ceid=...
    Inserts found articles into news_article table with source='burst_gnews'.
    """
    try:
        locale_params = _LOCALE_MAP.get(locale, _LOCALE_MAP["en"])
        query = " ".join(keywords)
        url = (
            f"https://news.google.com/rss/search"
            f"?q={quote_plus(query)}"
            f"&hl={locale_params['hl']}"
            f"&gl={locale_params['gl']}"
            f"&ceid={locale_params['ceid']}"
        )

        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)

        if resp.status_code != 200:
            logger.warning(
                "burst_gnews_fetch_failed",
                status=resp.status_code,
                keywords=keywords,
            )
            return []

        parsed = feedparser.parse(resp.text)
        articles: list[dict[str, Any]] = []

        for entry in parsed.entries:
            try:
                entry_url = entry.get("link", "")
                title = entry.get("title", "").strip()
                if not entry_url or not title:
                    continue

                uhash = _url_hash(entry_url)
                existing = await db_pool.fetchval(
                    "SELECT 1 FROM news_article WHERE url_hash = $1 LIMIT 1",
                    uhash,
                )
                if existing:
                    continue

                body = entry.get("summary", "").strip()
                cfp = _content_fp(title, body)
                published = _parse_entry_date(entry)

                await db_pool.execute(
                    "INSERT INTO news_article "
                    "(url, url_hash, content_fp, title, body, source, "
                    "author, publish_time, locale, category) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) "
                    "ON CONFLICT DO NOTHING",
                    entry_url,
                    uhash,
                    cfp,
                    title,
                    body,
                    "burst_gnews",
                    "",
                    published,
                    locale,
                    "general",
                )
                articles.append({"url": entry_url, "title": title})
            except Exception as exc:
                logger.warning(
                    "burst_gnews_entry_error",
                    error=str(exc),
                    title=entry.get("title", "?"),
                )
                continue

        logger.info(
            "burst_gnews_complete",
            keywords=keywords,
            new_articles=len(articles),
            total_entries=len(parsed.entries),
        )
        return articles
    except Exception as exc:
        logger.error("burst_gnews_failed", keywords=keywords, error=str(exc))
        return []


async def search_reddit(
    keywords: list[str],
    db_pool: asyncpg.Pool,
) -> list[dict[str, Any]]:
    """Search Reddit for posts matching keywords.

    URL: https://www.reddit.com/search.json?q={query}&sort=new&limit=25
    Inserts found items into news_article table with source='burst_reddit'.
    """
    try:
        query = " ".join(keywords)
        url = "https://www.reddit.com/search.json"
        params = {"q": query, "sort": "new", "limit": "25"}

        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = await client.get(url, params=params)

        if resp.status_code != 200:
            logger.warning(
                "burst_reddit_fetch_failed",
                status=resp.status_code,
                keywords=keywords,
            )
            return []

        data = resp.json()
        children = data.get("data", {}).get("children", [])
        articles: list[dict[str, Any]] = []

        for child in children:
            try:
                post = child.get("data", {})
                post_url = f"https://www.reddit.com{post.get('permalink', '')}"
                title = post.get("title", "").strip()
                if not title or not post.get("permalink"):
                    continue

                uhash = _url_hash(post_url)
                existing = await db_pool.fetchval(
                    "SELECT 1 FROM news_article WHERE url_hash = $1 LIMIT 1",
                    uhash,
                )
                if existing:
                    continue

                body = post.get("selftext", "")[:500]
                cfp = _content_fp(title, body)
                created_utc = post.get("created_utc", 0)
                published = datetime.fromtimestamp(created_utc, tz=timezone.utc)
                subreddit = post.get("subreddit", "unknown")

                await db_pool.execute(
                    "INSERT INTO news_article "
                    "(url, url_hash, content_fp, title, body, source, "
                    "author, publish_time, locale, category) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) "
                    "ON CONFLICT DO NOTHING",
                    post_url,
                    uhash,
                    cfp,
                    title,
                    body,
                    "burst_reddit",
                    f"r/{subreddit}",
                    published,
                    "en",
                    "general",
                )
                articles.append({"url": post_url, "title": title})
            except Exception as exc:
                logger.warning(
                    "burst_reddit_entry_error",
                    error=str(exc),
                )
                continue

        logger.info(
            "burst_reddit_complete",
            keywords=keywords,
            new_articles=len(articles),
            total_posts=len(children),
        )
        return articles
    except Exception as exc:
        logger.error("burst_reddit_failed", keywords=keywords, error=str(exc))
        return []


async def run_burst_crawl(
    keywords: list[str],
    locale: str,
    db_pool: asyncpg.Pool,
) -> int:
    """Execute burst crawl across all searchable sources.

    Returns total number of new articles found.
    """
    try:
        gnews_task = search_google_news_rss(keywords, locale, db_pool)
        reddit_task = search_reddit(keywords, db_pool)
        gnews_result, reddit_result = await asyncio.gather(
            gnews_task,
            reddit_task,
            return_exceptions=True,
        )

        total = 0
        if isinstance(gnews_result, list):
            total += len(gnews_result)
        else:
            logger.error(
                "burst_gnews_exception",
                error=str(gnews_result),
            )

        if isinstance(reddit_result, list):
            total += len(reddit_result)
        else:
            logger.error(
                "burst_reddit_exception",
                error=str(reddit_result),
            )

        logger.info(
            "burst_crawl_complete",
            keywords=keywords,
            locale=locale,
            total=total,
        )
        return total
    except Exception as exc:
        logger.error("burst_crawl_failed", keywords=keywords, error=str(exc))
        return 0


def _parse_entry_date(entry: Any) -> datetime:  # noqa: ANN401
    """Parse published date from RSS entry, fallback to now()."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        from time import mktime

        return datetime.fromtimestamp(
            mktime(entry.published_parsed),
            tz=timezone.utc,
        )
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        from time import mktime

        return datetime.fromtimestamp(
            mktime(entry.updated_parsed),
            tz=timezone.utc,
        )
    return datetime.now(tz=timezone.utc)
