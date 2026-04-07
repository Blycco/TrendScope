"""Cross-platform verification — boost trend scores confirmed across multiple sources.

Multiplier: 1 source = 1.0x, 2 = 1.1x, 3 = 1.2x, 4 = 1.3x, 5+ = 1.5x
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_MULTIPLIER_MAP: dict[int, float] = {
    1: 1.0,
    2: 1.1,
    3: 1.2,
    4: 1.3,
}
_MULTIPLIER_5_PLUS: float = 1.5


def verify_cross_platform(articles: list[dict[str, Any]]) -> float:
    """Return a score multiplier (1.0~1.5) based on source diversity.

    Counts unique source types from the ``source`` field of each article.
    Known source types include rss_ko, rss_en, dc_inside, fm_korea,
    burst_gnews, burst_reddit, etc.

    Args:
        articles: List of article dicts, each expected to have a ``source`` key.

    Returns:
        Multiplier in [1.0, 1.5].
    """
    if not articles:
        return 1.0

    unique_sources: set[str] = set()
    for article in articles:
        source = article.get("source")
        if source:
            unique_sources.add(str(source))

    count = len(unique_sources)
    if count >= 5:
        multiplier = _MULTIPLIER_5_PLUS
    else:
        multiplier = _MULTIPLIER_MAP.get(count, 1.0)

    logger.debug(
        "cross_platform_verified",
        unique_sources=count,
        multiplier=multiplier,
        sources=sorted(unique_sources),
    )
    return multiplier
