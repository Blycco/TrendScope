"""Brand monitoring: Z-score-based sentiment crisis detection.

RULE 02: asyncpg $1/$2 parameterization only — no f-string SQL.
RULE 06: all async functions have try/except + structlog logging.
RULE 07: type hints on all functions.
RULE 18: Redis cache TTL 900s (15 min) per spec.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import asyncpg
import structlog

from backend.processor.algorithms.sentiment import SentimentAnalyzer
from backend.processor.shared.cache_manager import get_cached, set_cached

logger = structlog.get_logger(__name__)

_CACHE_TTL = 900  # 15 minutes
_DEFAULT_ALERT_THRESHOLD = 2.0

_analyzer = SentimentAnalyzer()


@dataclass
class BrandMonitorRecord:
    """Row from brand_monitor table."""

    id: str
    user_id: str
    brand_name: str
    keywords: list[str]
    is_active: bool
    slack_webhook: str | None
    last_alerted_at: str | None


@dataclass
class BrandMonitorResult:
    """Result of a single brand monitoring evaluation."""

    brand_name: str
    current_score: float
    mean_24h: float
    std_24h: float
    z_score: float
    alert_threshold: float
    is_crisis: bool
    label: str
    cached: bool = False
    mentions: list[dict] = field(default_factory=list)


def calculate_zscore(
    current_score: float,
    mean_24h: float,
    std_24h: float,
) -> float:
    """Compute Z-score for the current sentiment score relative to 24h baseline.

    Args:
        current_score: Sentiment score for the current window.
        mean_24h: Mean sentiment score over the past 24 hours.
        std_24h: Standard deviation of sentiment score over the past 24 hours.

    Returns:
        Z-score, or 0.0 when std_24h is zero (no variance).
    """
    if std_24h == 0.0:
        return 0.0
    return (current_score - mean_24h) / std_24h


def _compute_stats(scores: list[float]) -> tuple[float, float]:
    """Return (mean, std) for a list of scores. Returns (0.0, 0.0) when empty."""
    if not scores:
        return 0.0, 0.0
    n = len(scores)
    mean = sum(scores) / n
    variance = sum((s - mean) ** 2 for s in scores) / n
    return mean, math.sqrt(variance)


async def _fetch_alert_threshold(pool: asyncpg.Pool) -> float:
    """Read brand.alert_threshold from admin_settings, defaulting to 2.0."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM admin_settings WHERE key = $1",
                "brand.alert_threshold",
            )
        if row is not None:
            raw = row["value"]
            if isinstance(raw, (int, float)):
                return float(raw)
            if isinstance(raw, dict) and "threshold" in raw:
                return float(raw["threshold"])
        logger.debug("brand_alert_threshold_db_miss_using_default")
        return _DEFAULT_ALERT_THRESHOLD
    except Exception as exc:
        logger.warning("brand_alert_threshold_fetch_failed", error=str(exc))
        return _DEFAULT_ALERT_THRESHOLD


async def _fetch_brand_record(
    pool: asyncpg.Pool,
    user_id: str,
    brand_name: str,
) -> BrandMonitorRecord | None:
    """Fetch brand_monitor row for the given user and brand name."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id::text, user_id::text, brand_name, keywords,
                       is_active, slack_webhook, last_alerted_at::text
                FROM brand_monitor
                WHERE user_id = $1::uuid
                  AND brand_name = $2
                  AND is_active = TRUE
                """,
                user_id,
                brand_name,
            )
        if row is None:
            return None
        return BrandMonitorRecord(
            id=row["id"],
            user_id=row["user_id"],
            brand_name=row["brand_name"],
            keywords=list(row["keywords"] or []),
            is_active=row["is_active"],
            slack_webhook=row["slack_webhook"],
            last_alerted_at=row["last_alerted_at"],
        )
    except Exception as exc:
        logger.error(
            "brand_record_fetch_failed",
            user_id=user_id,
            brand_name=brand_name,
            error=str(exc),
        )
        return None


async def _fetch_recent_scores(
    pool: asyncpg.Pool,
    brand_name: str,
    keywords: list[str],
) -> list[float]:
    """Fetch sentiment scores from the last 24h for brand keywords via sns_trend.

    Returns a list of sentiment proxy scores derived from existing burst_z values.
    Falls back to empty list on error.
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT keyword, burst_z, sentiment_badge
                FROM sns_trend
                WHERE keyword = ANY($1::text[])
                  AND snapshot_at >= now() - INTERVAL '24 hours'
                ORDER BY snapshot_at DESC
                LIMIT 200
                """,
                keywords if keywords else [brand_name],
            )
        scores: list[float] = []
        for row in rows:
            badge = row["sentiment_badge"] or "neutral"
            raw_z = float(row["burst_z"] or 0.0)
            if badge == "positive":
                scores.append(min(1.0, abs(raw_z) / 5.0))
            elif badge == "negative":
                scores.append(-min(1.0, abs(raw_z) / 5.0))
            else:
                scores.append(0.0)
        return scores
    except Exception as exc:
        logger.warning(
            "brand_recent_scores_fetch_failed",
            brand_name=brand_name,
            error=str(exc),
        )
        return []


async def monitor_brand(
    pool: asyncpg.Pool,
    user_id: str,
    brand_name: str,
    texts: list[str],
) -> BrandMonitorResult:
    """Evaluate brand sentiment crisis using Z-score detection.

    Analyzes the provided texts, computes a mean sentiment score, compares it
    against the 24-hour baseline from DB, and flags a crisis when
    |Z-score| > alert_threshold.

    Results are cached in Redis under ``brand:{uid}:{name}`` with TTL 900s.

    Args:
        pool: Active asyncpg connection pool.
        user_id: UUID string of the requesting user.
        brand_name: Name of the brand being monitored.
        texts: Recent text snippets mentioning the brand.

    Returns:
        BrandMonitorResult with crisis flag and Z-score details.
    """
    cache_key = f"brand:{user_id}:{brand_name.lower()}"

    try:
        cached_bytes = await get_cached(cache_key)
        if cached_bytes is not None:
            try:
                raw = json.loads(cached_bytes)
                logger.debug("brand_monitor_cache_hit", brand_name=brand_name)
                return BrandMonitorResult(
                    brand_name=raw["brand_name"],
                    current_score=raw["current_score"],
                    mean_24h=raw["mean_24h"],
                    std_24h=raw["std_24h"],
                    z_score=raw["z_score"],
                    alert_threshold=raw["alert_threshold"],
                    is_crisis=raw["is_crisis"],
                    label=raw["label"],
                    cached=True,
                    mentions=raw.get("mentions", []),
                )
            except Exception as parse_exc:
                logger.warning("brand_monitor_cache_parse_failed", error=str(parse_exc))
    except Exception as exc:
        logger.warning("brand_monitor_cache_get_failed", error=str(exc))

    try:
        record = await _fetch_brand_record(pool, user_id, brand_name)
        keywords = record.keywords if record else [brand_name]

        alert_threshold = await _fetch_alert_threshold(pool)

        # Compute current sentiment score from provided texts
        mentions: list[dict] = []
        if texts:
            sentiment_scores: list[float] = []
            for text in texts:
                result = _analyzer.analyze(text)
                signed = (
                    result.score
                    if result.label == "positive"
                    else (-result.score if result.label == "negative" else 0.0)
                )
                sentiment_scores.append(signed)
                mentions.append({"text": text[:100], "label": result.label, "score": result.score})
            current_score = sum(sentiment_scores) / len(sentiment_scores)
        else:
            current_score = 0.0

        # Fetch 24h historical scores
        historical_scores = await _fetch_recent_scores(pool, brand_name, keywords)
        mean_24h, std_24h = _compute_stats(historical_scores)

        z_score = calculate_zscore(current_score, mean_24h, std_24h)
        is_crisis = abs(z_score) > alert_threshold

        # Derive human-readable label
        if is_crisis and z_score < 0:
            label = "crisis"
        elif is_crisis and z_score > 0:
            label = "surge"
        else:
            label = "normal"

        monitor_result = BrandMonitorResult(
            brand_name=brand_name,
            current_score=current_score,
            mean_24h=mean_24h,
            std_24h=std_24h,
            z_score=z_score,
            alert_threshold=alert_threshold,
            is_crisis=is_crisis,
            label=label,
            cached=False,
            mentions=mentions,
        )

        try:
            payload = json.dumps(
                {
                    "brand_name": monitor_result.brand_name,
                    "current_score": monitor_result.current_score,
                    "mean_24h": monitor_result.mean_24h,
                    "std_24h": monitor_result.std_24h,
                    "z_score": monitor_result.z_score,
                    "alert_threshold": monitor_result.alert_threshold,
                    "is_crisis": monitor_result.is_crisis,
                    "label": monitor_result.label,
                    "mentions": monitor_result.mentions,
                }
            )
            await set_cached(cache_key, payload, _CACHE_TTL)
        except Exception as cache_exc:
            logger.warning("brand_monitor_cache_set_failed", error=str(cache_exc))

        logger.info(
            "brand_monitor_evaluated",
            brand_name=brand_name,
            user_id=user_id,
            z_score=round(z_score, 4),
            is_crisis=is_crisis,
            label=label,
        )
        return monitor_result

    except Exception as exc:
        logger.error(
            "brand_monitor_failed",
            user_id=user_id,
            brand_name=brand_name,
            error=str(exc),
        )
        raise
