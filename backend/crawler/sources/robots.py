"""robots.txt compliance checker with Redis caching. (RULE 18: cache aggressively)"""

from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
import structlog

from backend.processor.shared.cache_manager import get_cached, set_cached

logger = structlog.get_logger(__name__)

_ROBOTS_CACHE_TTL = 3600  # 1 hour
_USER_AGENT = "TrendScopeBot"


async def is_allowed(url: str, user_agent: str = _USER_AGENT) -> bool:
    """Check whether the URL is allowed by the domain's robots.txt.

    Fetches and caches robots.txt per domain with 1-hour TTL.
    On fetch error, defaults to allowed (True) with a warning.
    """
    try:
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        cache_key = f"robots:{parsed.netloc}"

        robots_text = await _get_robots_text(domain, cache_key)
        if robots_text is None:
            return True

        parser = RobotFileParser()
        parser.parse(robots_text.splitlines())
        return parser.can_fetch(user_agent, url)
    except Exception as exc:
        logger.warning("robots_check_failed", url=url, error=str(exc))
        return True


async def _get_robots_text(domain: str, cache_key: str) -> str | None:
    """Fetch robots.txt, using Redis cache when available."""
    try:
        cached = await get_cached(cache_key)
        if cached is not None:
            return cached.decode("utf-8") if isinstance(cached, bytes) else cached

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{domain}/robots.txt")

        if resp.status_code != 200:
            logger.info("robots_not_found", domain=domain, status=resp.status_code)
            await set_cached(cache_key, b"", _ROBOTS_CACHE_TTL)
            return None

        text = resp.text
        await set_cached(cache_key, text.encode("utf-8"), _ROBOTS_CACHE_TTL)
        return text
    except Exception as exc:
        logger.warning("robots_fetch_failed", domain=domain, error=str(exc))
        return None
