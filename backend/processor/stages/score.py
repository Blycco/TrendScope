"""Stage 6: Score clusters and compute early trend signals. (RULE 06: try/except + structlog)"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

import structlog

from backend.processor.algorithms.cross_platform import verify_cross_platform
from backend.processor.shared.score_calculator import ScoreInput, ScoreResult, calculate_score
from backend.processor.shared.semantic_clusterer import Cluster

logger = structlog.get_logger(__name__)


def compute_early_trend_score(articles: list[dict[str, Any]]) -> float:
    """Compute a lightweight early trend score from cluster article data.

    Combines three signals:
    - velocity: normalized article count (more articles = faster growing)
    - source_diversity: ratio of unique sources (broader coverage = stronger signal)
    - recency: how recent the newest article is (newer = more likely emerging)

    Returns a score in [0.0, 1.0].
    """
    if not articles:
        return 0.0

    # Velocity: article count normalized (10+ articles → 1.0)
    velocity = min(1.0, len(articles) / 10.0)

    # Source diversity: unique sources / total articles
    sources = {a.get("source", "") for a in articles if a.get("source")}
    source_diversity = len(sources) / max(len(articles), 1)

    # Recency: newest article within last 6 hours → 1.0, 48h+ → 0.0
    now = datetime.now(tz=timezone.utc)
    newest_hours = 48.0
    for a in articles:
        pub_time = a.get("publish_time")
        if isinstance(pub_time, str):
            pub_time = datetime.fromisoformat(pub_time)
        if isinstance(pub_time, datetime):
            hours_ago = (now - pub_time).total_seconds() / 3600
            newest_hours = min(newest_hours, max(0.0, hours_ago))
    recency = max(0.0, 1.0 - (newest_hours / 48.0))

    return round(0.4 * velocity + 0.3 * source_diversity + 0.3 * recency, 4)


def stage_score(clusters: list[Cluster]) -> list[dict[str, Any]]:
    """Stage 6: Calculate score for each cluster."""
    scored: list[dict[str, Any]] = []
    for cluster in clusters:
        try:
            articles: list[dict[str, Any]] = getattr(cluster, "_articles", [])
            rep_article = articles[0] if articles else {}

            pub_time = rep_article.get("publish_time", datetime.now(tz=timezone.utc))
            if isinstance(pub_time, str):
                pub_time = datetime.fromisoformat(pub_time)

            # Count unique sources for normalized scoring
            sources = {a.get("source", "") for a in articles if a.get("source")}
            source_count = max(1, len(sources))

            score_input = ScoreInput(
                published_at=pub_time,
                category=rep_article.get("category", "default"),
                source_type=rep_article.get("source", "default"),
                article_count=len(articles),
                source_count=source_count,
                keyword_importance=rep_article.get("keyword_importance", 0.0),
            )
            result: ScoreResult = calculate_score(score_input)

            keyword_counter: Counter[str] = Counter()
            for a in articles:
                for kw in a.get("keywords", []):
                    if not kw.isdigit() and len(kw) >= 2:
                        keyword_counter[kw] += 1
            unique_keywords = [kw for kw, _ in keyword_counter.most_common(20)]

            top_keywords = unique_keywords[:3]
            group_title = " · ".join(top_keywords) if top_keywords else rep_article.get("title", "")

            early_score = compute_early_trend_score(articles)

            cross_platform_multiplier = verify_cross_platform(articles)

            scored.append(
                {
                    "cluster": cluster,
                    "articles": articles,
                    "score": min(100.0, result.normalized * cross_platform_multiplier),
                    "cross_platform_multiplier": cross_platform_multiplier,
                    "early_trend_score": early_score,
                    "title": group_title,
                    "category": rep_article.get("category", "general"),
                    "locale": rep_article.get("locale", "ko"),
                    "keywords": unique_keywords,
                }
            )
        except Exception as exc:
            logger.warning("pipeline_score_error", error=str(exc))
            continue
    return scored
