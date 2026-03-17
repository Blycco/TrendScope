"""Article body extraction with 3-stage fallback."""

from __future__ import annotations

import httpx
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


async def extract_body(url: str, html: str | None = None) -> str:
    """Extract article body text with 3-stage fallback.

    Stage 1: newspaper3k
    Stage 2: readability-lxml
    Stage 3: BeautifulSoup raw tag stripping (always succeeds)

    If *html* is provided, skip the HTTP fetch.
    """
    if html is None:
        html = await _fetch_html(url)
        if not html:
            return ""

    # Stage 1: newspaper3k
    body = _stage1_newspaper(url, html)
    if body:
        logger.debug("extractor_stage1_ok", url=url, length=len(body))
        return body

    # Stage 2: readability-lxml
    body = _stage2_readability(url, html)
    if body:
        logger.debug("extractor_stage2_ok", url=url, length=len(body))
        return body

    # Stage 3: BeautifulSoup strip tags
    body = _stage3_bs4(html)
    logger.debug("extractor_stage3_fallback", url=url, length=len(body))
    return body


async def _fetch_html(url: str) -> str:
    """Fetch raw HTML from URL."""
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "TrendScopeBot/1.0"},
        ) as client:
            resp = await client.get(url)
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
        if len(text) > 50:
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
        if len(text) > 50:
            return text
        return ""
    except Exception as exc:
        logger.debug("extractor_stage2_failed", url=url, error=str(exc))
        return ""


def _stage3_bs4(html: str) -> str:
    """Stage 3: raw HTML tag stripping with BeautifulSoup."""
    try:
        soup = BeautifulSoup(html, "lxml")
        _BOILERPLATE = ["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]
        for tag in soup(_BOILERPLATE):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text
    except Exception as exc:
        logger.debug("extractor_stage3_failed", error=str(exc))
        return ""
