"""Article body extraction with 3-stage fallback."""

from __future__ import annotations

import asyncio

import httpx
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)

_MIN_BODY_LENGTH = 50


async def extract_body(
    url: str,
    html: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Extract article body text with 3-stage fallback.

    Stage 1: newspaper3k
    Stage 2: readability-lxml
    Stage 3: BeautifulSoup raw tag stripping

    If *html* is provided, skip the HTTP fetch.
    If *client* is provided and *html* is None, reuse client for fetching.
    """
    if html is None:
        html = await _fetch_html(url, client=client)
        if not html:
            return ""

    # Stage 1: newspaper3k
    body = await asyncio.to_thread(_stage1_newspaper, url, html)
    if body:
        logger.debug("extractor_stage1_ok", url=url, length=len(body))
        return body

    # Stage 2: readability-lxml
    body = await asyncio.to_thread(_stage2_readability, url, html)
    if body:
        logger.debug("extractor_stage2_ok", url=url, length=len(body))
        return body

    # Stage 3: BeautifulSoup strip tags
    body = await asyncio.to_thread(_stage3_bs4, html)
    if body:
        logger.debug("extractor_stage3_fallback", url=url, length=len(body))
        return body

    logger.warning("extractor_all_stages_failed", url=url)
    return ""


async def _fetch_html(
    url: str,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Fetch raw HTML from URL. Reuse *client* if provided."""
    try:
        if client is not None:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "TrendScopeBot/1.0"},
        ) as c:
            resp = await c.get(url)
            resp.raise_for_status()
            return resp.text
    except Exception as exc:
        logger.warning("extractor_fetch_failed", url=url, error=str(exc))
        return ""


def _stage1_newspaper(url: str, html: str) -> str:
    """Stage 1: newspaper3k extraction."""
    try:
        from newspaper import Article, ArticleException

        article = Article(url)
        article.download(input_html=html)
        article.parse()
        text = (article.text or "").strip()
        if len(text) >= _MIN_BODY_LENGTH:
            return text
        return ""
    except (ArticleException, Exception) as exc:
        logger.debug("extractor_stage1_failed", url=url, error=str(exc))
        return ""


def _stage2_readability(url: str, html: str) -> str:
    """Stage 2: readability-lxml extraction."""
    try:
        from readability import Document

        doc = Document(html)
        summary_html = doc.summary()
        soup = BeautifulSoup(summary_html, "lxml")
        text = soup.get_text(separator="\n", strip=True)
        if len(text) >= _MIN_BODY_LENGTH:
            return text
        return ""
    except Exception as exc:
        logger.debug("extractor_stage2_failed", url=url, error=str(exc))
        return ""


def _stage3_bs4(html: str) -> str:
    """Stage 3: raw HTML tag stripping with BeautifulSoup."""
    try:
        soup = BeautifulSoup(html, "lxml")
        _BOILERPLATE = [
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "aside",
            "iframe",
            "noscript",
        ]
        for tag in soup(_BOILERPLATE):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        if len(text) >= _MIN_BODY_LENGTH:
            return text
        return ""
    except Exception as exc:
        logger.debug("extractor_stage3_failed", error=str(exc))
        return ""
