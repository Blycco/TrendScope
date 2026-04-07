"""Burst Job orchestrator — trigger focused crawl for emerging trends."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Any

import asyncpg
import structlog

from backend.crawler.sources.burst_crawler import run_burst_crawl
from backend.processor.algorithms.seasonality import detect_seasonality
from backend.processor.shared.cache_manager import get_cached, get_redis, set_cached

logger = structlog.get_logger(__name__)

_BURST_LOCK_KEY = "burst_job_running"
_BURST_LOCK_TTL = 1800  # 30 minutes
_MAX_CANDIDATES = 3
_MAX_KEYWORDS_PER_GROUP = 3
_SETTINGS_CACHE_TTL = 300  # 5 minutes
_DEFAULT_THRESHOLD = 0.75
_DEFAULT_COOLDOWN_HOURS = 2


async def _acquire_burst_lock() -> bool:
    """Acquire Redis lock with 30-minute TTL for burst rate limiting."""
    try:
        redis = get_redis()
        result = await redis.set(
            f"lock:{_BURST_LOCK_KEY}",
            "1",
            nx=True,
            ex=_BURST_LOCK_TTL,
        )
        return result is not None
    except Exception as exc:
        logger.warning("burst_lock_acquire_failed", error=str(exc))
        return False


async def _release_burst_lock() -> None:
    """Release the burst lock."""
    try:
        redis = get_redis()
        await redis.delete(f"lock:{_BURST_LOCK_KEY}")
    except Exception as exc:
        logger.warning("burst_lock_release_failed", error=str(exc))


async def _get_setting(pool: asyncpg.Pool, key: str, default: str) -> str:
    """Read a setting from admin_settings with cache."""
    cache_key = f"burst_setting:{key}"
    cached = await get_cached(cache_key)
    if cached is not None:
        return cached.decode("utf-8") if isinstance(cached, bytes) else str(cached)
    try:
        row = await pool.fetchval(
            "SELECT value FROM admin_settings WHERE key = $1",
            key,
        )
        value = json.loads(row) if row is not None else default
        await set_cached(cache_key, str(value).encode(), _SETTINGS_CACHE_TTL)
        return str(value)
    except Exception as exc:
        logger.warning("burst_setting_read_failed", key=key, error=str(exc))
        return default


async def get_burst_threshold(pool: asyncpg.Pool) -> float:
    """Read burst_threshold from admin_settings, default 0.75."""
    return float(await _get_setting(pool, "burst_threshold", str(_DEFAULT_THRESHOLD)))


async def get_burst_cooldown(pool: asyncpg.Pool) -> int:
    """Read burst_cooldown_hours from admin_settings, default 2."""
    return int(
        float(await _get_setting(pool, "burst_cooldown_hours", str(_DEFAULT_COOLDOWN_HOURS)))
    )


async def _fetch_keyword_history(
    pool: asyncpg.Pool,
    keyword: str,
) -> list[tuple[datetime, float]]:
    """Fetch historical frequency data for a keyword from news_group.

    Returns list of (created_at, early_trend_score) tuples.
    """
    try:
        rows = await pool.fetch(
            """
            SELECT ng.created_at, ng.early_trend_score
            FROM news_group ng
            WHERE $1 = ANY(ng.keywords)
            ORDER BY ng.created_at ASC
            """,
            keyword,
        )
        return [(row["created_at"], float(row["early_trend_score"])) for row in rows]
    except Exception as exc:
        logger.warning("keyword_history_fetch_failed", keyword=keyword, error=str(exc))
        return []


async def _check_seasonality(
    pool: asyncpg.Pool,
    keywords: list[str],
) -> bool:
    """Check if any of the keywords show seasonal patterns."""
    try:
        for keyword in keywords:
            history = await _fetch_keyword_history(pool, keyword)
            if detect_seasonality(keyword, history):
                return True
        return False
    except Exception as exc:
        logger.warning("seasonality_check_failed", error=str(exc))
        return False


async def find_burst_candidates(
    pool: asyncpg.Pool,
    threshold: float,
    cooldown_hours: int,
) -> list[asyncpg.Record]:
    """Find news_groups above threshold without recent burst jobs."""
    try:
        return await pool.fetch(
            """
            SELECT ng.id, ng.keywords, ng.locale, ng.early_trend_score
            FROM news_group ng
            WHERE ng.early_trend_score >= $1
              AND ng.created_at > now() - INTERVAL '48 hours'
              AND NOT EXISTS (
                  SELECT 1 FROM burst_job_log bjl
                  WHERE bjl.group_id = ng.id
                    AND bjl.triggered_at > now() - make_interval(hours => $2)
                    AND bjl.status IN ('running', 'success')
              )
            ORDER BY ng.early_trend_score DESC
            LIMIT $3
            """,
            threshold,
            cooldown_hours,
            _MAX_CANDIDATES,
        )
    except Exception as exc:
        logger.error("burst_find_candidates_failed", error=str(exc))
        return []


async def log_burst_job(
    pool: asyncpg.Pool,
    *,
    trigger_source: str,
    group_id: uuid.UUID | None,
    keywords: list[str],
    threshold: float,
    early_trend_score: float,
) -> int:
    """Insert a burst_job_log row with status='running'. Returns the log ID."""
    try:
        return await pool.fetchval(
            """
            INSERT INTO burst_job_log
                (trigger_source, group_id, keywords, threshold,
                 early_trend_score, status)
            VALUES ($1, $2, $3, $4, $5, 'running')
            RETURNING id
            """,
            trigger_source,
            group_id,
            keywords,
            threshold,
            early_trend_score,
        )
    except Exception as exc:
        logger.error("burst_log_insert_failed", error=str(exc))
        return 0


async def update_burst_log(
    pool: asyncpg.Pool,
    log_id: int,
    *,
    status: str,
    articles_found: int,
    duration_ms: float,
    error_detail: str | None = None,
) -> None:
    """Update burst_job_log with final status."""
    try:
        await pool.execute(
            """
            UPDATE burst_job_log
            SET status = $1, articles_found = $2, duration_ms = $3,
                error_detail = $4, completed_at = now()
            WHERE id = $5
            """,
            status,
            articles_found,
            duration_ms,
            error_detail,
            log_id,
        )
    except Exception as exc:
        logger.error("burst_log_update_failed", log_id=log_id, error=str(exc))


async def run_burst_job(
    pool: asyncpg.Pool,
    *,
    trigger_source: str = "auto",
) -> int:
    """Main burst job entry point.

    1. Acquire Redis lock (30-min TTL)
    2. Read threshold from admin_settings
    3. Find candidate groups above threshold
    4. For each candidate (max 3): crawl with top keywords
    5. Release lock

    Returns count of burst jobs triggered.
    """
    if not await _acquire_burst_lock():
        logger.info("burst_job_skipped_lock_held")
        return 0

    try:
        threshold = await get_burst_threshold(pool)
        cooldown = await get_burst_cooldown(pool)
        candidates = await find_burst_candidates(pool, threshold, cooldown)

        if not candidates:
            logger.info("burst_job_no_candidates", threshold=threshold)
            return 0

        triggered = 0
        for row in candidates:
            keywords = list(row["keywords"][:_MAX_KEYWORDS_PER_GROUP])
            if not keywords:
                continue

            # Filter out noise: short terms, pure digits
            keywords = [k for k in keywords if len(k) >= 2 and not k.isdigit()]
            if not keywords:
                continue

            locale = row["locale"] or "ko"
            score = float(row["early_trend_score"])
            group_id = row["id"]

            is_seasonal = await _check_seasonality(pool, keywords)
            if is_seasonal:
                logger.info(
                    "burst_candidate_seasonal",
                    group_id=str(group_id),
                    keywords=keywords,
                )

            log_id = await log_burst_job(
                pool,
                trigger_source=trigger_source,
                group_id=group_id,
                keywords=keywords,
                threshold=threshold,
                early_trend_score=score,
            )

            t0 = time.monotonic()
            try:
                articles_found = await run_burst_crawl(keywords, locale, pool)
                duration_ms = (time.monotonic() - t0) * 1000
                await update_burst_log(
                    pool,
                    log_id,
                    status="success",
                    articles_found=articles_found,
                    duration_ms=duration_ms,
                )
                triggered += 1
                logger.info(
                    "burst_job_triggered",
                    group_id=str(group_id),
                    keywords=keywords,
                    articles_found=articles_found,
                    duration_ms=round(duration_ms, 1),
                    is_seasonal=is_seasonal,
                )
            except Exception as exc:
                duration_ms = (time.monotonic() - t0) * 1000
                await update_burst_log(
                    pool,
                    log_id,
                    status="failed",
                    articles_found=0,
                    duration_ms=duration_ms,
                    error_detail=str(exc),
                )
                logger.error(
                    "burst_job_crawl_failed",
                    group_id=str(group_id),
                    error=str(exc),
                )

        logger.info("burst_job_complete", triggered=triggered)
        return triggered
    except Exception as exc:
        logger.error("burst_job_failed", error=str(exc))
        return 0
    finally:
        await _release_burst_lock()


async def manual_burst_trigger(
    pool: asyncpg.Pool,
    keywords: list[str],
    locale: str = "ko",
) -> dict[str, Any]:
    """Manual burst trigger for admin endpoint.

    Bypasses threshold check but respects rate limiting (Redis lock).
    Returns summary dict.
    """
    if not await _acquire_burst_lock():
        return {"success": False, "error": "rate_limited"}

    try:
        log_id = await log_burst_job(
            pool,
            trigger_source="manual",
            group_id=None,
            keywords=keywords,
            threshold=0.0,
            early_trend_score=0.0,
        )

        t0 = time.monotonic()
        try:
            articles_found = await run_burst_crawl(keywords, locale, pool)
            duration_ms = (time.monotonic() - t0) * 1000
            await update_burst_log(
                pool,
                log_id,
                status="success",
                articles_found=articles_found,
                duration_ms=duration_ms,
            )
            return {
                "success": True,
                "articles_found": articles_found,
                "duration_ms": round(duration_ms, 1),
                "log_id": log_id,
            }
        except Exception as exc:
            duration_ms = (time.monotonic() - t0) * 1000
            await update_burst_log(
                pool,
                log_id,
                status="failed",
                articles_found=0,
                duration_ms=duration_ms,
                error_detail=str(exc),
            )
            logger.error("manual_burst_crawl_failed", error=str(exc))
            return {"success": False, "error": str(exc), "log_id": log_id}
    except Exception as exc:
        logger.error("manual_burst_trigger_failed", error=str(exc))
        return {"success": False, "error": str(exc)}
    finally:
        await _release_burst_lock()
