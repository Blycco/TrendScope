"""Stage 6: Score clusters and compute early trend signals. (RULE 06: try/except + structlog)"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

import asyncpg
import structlog

from backend.processor.algorithms.burst import (
    BurstLevel,
    BurstResult,
    TimeSeriesPoint,
    detect_burst,
)
from backend.processor.algorithms.cross_platform import verify_cross_platform
from backend.processor.algorithms.external_trends import verify_external_trends
from backend.processor.algorithms.growth_classifier import (
    VelocityWindow,
    classify_growth_type,
)
from backend.processor.shared.score_calculator import (
    ScoreInput,
    ScoreResult,
    ScoreWeights,
    calculate_score,
)
from backend.processor.shared.semantic_clusterer import Cluster

logger = structlog.get_logger(__name__)

_DEFAULT_WEIGHTS = ScoreWeights()

# Momentum velocity constants
_ACCELERATION_DIVISOR = 5.0  # 5x acceleration = max velocity (1.0)
_MIN_HOURLY_AVG = 0.1  # Floor to avoid division by zero


def _parse_article_time(article: dict[str, Any]) -> datetime | None:
    """Parse publish_time from article dict, normalizing timezone."""
    pub_time = article.get("publish_time")
    if isinstance(pub_time, str):
        pub_time = datetime.fromisoformat(pub_time)
    if isinstance(pub_time, datetime):
        if pub_time.tzinfo is None:
            pub_time = pub_time.replace(tzinfo=timezone.utc)
        return pub_time
    return None


def _compute_momentum_velocity(
    articles: list[dict[str, Any]],
    now: datetime | None = None,
) -> float:
    """Compute momentum-based velocity from article publish times.

    Measures acceleration: recent 1-hour article rate vs 24-hour average.
    Returns a value in [0.0, 1.0] where 1.0 = 5x or more acceleration.
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)
    cnt_1h = 0
    cnt_24h = 0
    for a in articles:
        pt = _parse_article_time(a)
        if pt is None:
            continue
        elapsed = (now - pt).total_seconds()
        if elapsed < 3600:
            cnt_1h += 1
        if elapsed < 86400:
            cnt_24h += 1
    hourly_avg = cnt_24h / 24.0
    acceleration = cnt_1h / max(hourly_avg, _MIN_HOURLY_AVG)
    return min(1.0, acceleration / _ACCELERATION_DIVISOR)


def compute_early_trend_score(articles: list[dict[str, Any]]) -> float:
    """Compute a lightweight early trend score from cluster article data.

    Combines three signals:
    - velocity: momentum-based acceleration (recent 1h vs 24h average)
    - source_diversity: ratio of unique sources (broader coverage = stronger signal)
    - recency: how recent the newest article is (newer = more likely emerging)

    Returns a score in [0.0, 1.0].
    """
    if not articles:
        return 0.0

    # Source diversity: unique sources / total articles
    sources = {a.get("source", "") for a in articles if a.get("source")}
    if len(sources) < 2:
        return 0.0  # Single source is not an emerging trend

    now = datetime.now(tz=timezone.utc)
    velocity = _compute_momentum_velocity(articles, now)
    source_diversity = len(sources) / max(len(articles), 1)

    # Recency: newest article within last 6 hours → 1.0, 48h+ → 0.0
    newest_hours = 48.0
    for a in articles:
        pt = _parse_article_time(a)
        if pt is not None:
            hours_ago = (now - pt).total_seconds() / 3600
            newest_hours = min(newest_hours, max(0.0, hours_ago))
    recency = max(0.0, 1.0 - (newest_hours / 48.0))

    score = round(0.4 * velocity + 0.3 * source_diversity + 0.3 * recency, 4)
    # Cap score for very small clusters below display threshold
    if len(articles) < 3:
        score = min(score, 0.3)
    return score


def _build_velocity_windows(
    articles: list[dict[str, Any]],
    window_hours: int = 12,
    num_windows: int = 3,
    now: datetime | None = None,
) -> list[VelocityWindow]:
    """Build 12h velocity windows (newest → oldest) for growth classification."""
    if now is None:
        now = datetime.now(tz=timezone.utc)
    buckets = [0] * num_windows
    for a in articles:
        pt = _parse_article_time(a)
        if pt is None:
            continue
        hours_ago = (now - pt).total_seconds() / 3600
        if hours_ago < 0:
            continue
        idx = int(hours_ago // window_hours)
        if 0 <= idx < num_windows:
            buckets[idx] += 1
    return [
        VelocityWindow(
            window_start_hours_ago=i * window_hours,
            window_end_hours_ago=(i + 1) * window_hours,
            article_count=buckets[i],
        )
        for i in range(num_windows)
    ]


def _build_burst_series(articles: list[dict[str, Any]]) -> list[TimeSeriesPoint]:
    """Build a time series from article publish times for burst detection."""
    from collections import Counter

    hour_counts: Counter[float] = Counter()
    for a in articles:
        pt = _parse_article_time(a)
        if pt is not None:
            bucket = float(int(pt.timestamp() / 3600) * 3600)
            hour_counts[bucket] += 1

    return [
        TimeSeriesPoint(timestamp=ts, value=float(cnt)) for ts, cnt in sorted(hour_counts.items())
    ]


async def _load_weights(db_pool: asyncpg.Pool) -> ScoreWeights:
    """Load score weights from DB/Redis; falls back to defaults on error."""
    from backend.processor.shared.config_loader import get_setting

    d = _DEFAULT_WEIGHTS
    return ScoreWeights(
        freshness=float(await get_setting(db_pool, "score.weight_freshness", d.freshness)),
        burst=float(await get_setting(db_pool, "score.weight_burst", d.burst)),
        article_count=float(
            await get_setting(db_pool, "score.weight_article_count", d.article_count)
        ),
        source_diversity=float(
            await get_setting(db_pool, "score.weight_source_diversity", d.source_diversity)
        ),
        social_signal=float(await get_setting(db_pool, "score.weight_social", d.social_signal)),
        keyword_importance=float(
            await get_setting(db_pool, "score.weight_keyword", d.keyword_importance)
        ),
        velocity=float(await get_setting(db_pool, "score.weight_velocity", d.velocity)),
    )


async def stage_score(
    clusters: list[Cluster],
    db_pool: asyncpg.Pool,
) -> list[dict[str, Any]]:
    """Stage 6: Calculate score for each cluster."""
    try:
        weights = await _load_weights(db_pool)
    except Exception as exc:
        logger.warning("score_weights_load_failed", error=str(exc))
        weights = _DEFAULT_WEIGHTS

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

            # Burst detection (skip for sparse time series to avoid noise)
            series = _build_burst_series(articles)
            _MIN_BURST_SERIES = 5
            if len(series) >= _MIN_BURST_SERIES:
                burst_result = detect_burst(series)
            else:
                burst_result = BurstResult(
                    score=0.0,
                    level=BurstLevel.END,
                    prophet_score=0.0,
                    iforest_score=0.0,
                    cusum_score=0.0,
                    growth_type="unknown",
                )
            early_velocity = _compute_momentum_velocity(articles)

            velocity_windows = _build_velocity_windows(articles)
            classified_growth = classify_growth_type(velocity_windows).value

            score_input = ScoreInput(
                published_at=pub_time,
                category=rep_article.get("category", "default"),
                source_type=rep_article.get("source", "default"),
                article_count=len(articles),
                source_count=source_count,
                keyword_importance=rep_article.get("keyword_importance", 0.0),
                burst_score=burst_result.score,
                velocity=early_velocity,
            )
            result: ScoreResult = calculate_score(score_input, weights=weights)

            keyword_counter: Counter[str] = Counter()
            for a in articles:
                for kw in a.get("keywords", []):
                    if not kw.isdigit() and len(kw) >= 2:
                        keyword_counter[kw] += 1
            unique_keywords = [kw for kw, _ in keyword_counter.most_common(20)]

            # Group title: prefer rep article's original title
            raw_title = rep_article.get("title", "")
            if raw_title:
                group_title = raw_title if len(raw_title) <= 50 else raw_title[:45] + "…"
            else:
                group_title = " · ".join(unique_keywords[:3])

            early_score = compute_early_trend_score(articles)
            cross_platform_multiplier = verify_cross_platform(articles)
            external_boost = await verify_external_trends(
                db_pool,
                unique_keywords,
                locale=rep_article.get("locale", "ko"),
            )

            scored.append(
                {
                    "cluster": cluster,
                    "articles": articles,
                    "score": min(
                        100.0,
                        result.normalized * cross_platform_multiplier * external_boost,
                    ),
                    "cross_platform_multiplier": cross_platform_multiplier,
                    "external_trend_boost": external_boost,
                    "early_trend_score": early_score,
                    "title": group_title,
                    "category": rep_article.get("category", "general"),
                    "locale": rep_article.get("locale", "ko"),
                    "keywords": unique_keywords,
                    "burst_score": burst_result.score,
                    "growth_type": (
                        classified_growth
                        if classified_growth != "unknown"
                        else burst_result.growth_type
                    ),
                }
            )
        except Exception as exc:
            logger.warning("pipeline_score_error", error=str(exc))
            continue
    return scored
