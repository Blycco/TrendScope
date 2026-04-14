"""APScheduler job definitions for TrendScope crawlers."""

from __future__ import annotations

import asyncpg
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.crawler.quota_guard import reset_all_quotas
from backend.crawler.sources.community_crawler import crawl_all as community_crawl_all
from backend.crawler.sources.naver_datalab_crawler import crawl_naver_datalab
from backend.crawler.sources.news_crawler import crawl_all as news_crawl_all
from backend.crawler.sources.sns_crawler import collect_all as sns_collect_all
from backend.jobs.brand_alert import run_brand_alert
from backend.jobs.burst_job import run_burst_job
from backend.jobs.digest_job import run_daily_digest
from backend.jobs.early_trend_update import run_early_trend_update
from backend.jobs.keyword_review_job import run_keyword_review_job
from backend.jobs.keyword_snapshot_job import run_keyword_snapshot
from backend.jobs.plan_expiry import run_plan_expiry

logger = structlog.get_logger(__name__)


async def _job_news_crawl(db_pool: asyncpg.Pool) -> None:
    """Scheduled job: crawl all news feeds."""
    try:
        articles = await news_crawl_all(db_pool)
        logger.info("scheduled_news_crawl_done", new_articles=len(articles))
    except Exception as exc:
        logger.error("scheduled_news_crawl_failed", error=str(exc))


async def _job_sns_collect(db_pool: asyncpg.Pool) -> None:
    """Scheduled job: collect from all SNS sources."""
    try:
        items = await sns_collect_all(db_pool)
        logger.info("scheduled_sns_collect_done", items=len(items))
    except Exception as exc:
        logger.error("scheduled_sns_collect_failed", error=str(exc))


async def _job_community_crawl(db_pool: asyncpg.Pool) -> None:
    """Scheduled job: crawl community sources."""
    try:
        articles = await community_crawl_all(db_pool)
        logger.info("scheduled_community_crawl_done", articles=len(articles))
    except Exception as exc:
        logger.error("scheduled_community_crawl_failed", error=str(exc))


async def _job_early_trend_update(db_pool: asyncpg.Pool) -> None:
    """Scheduled job: recalculate early_trend_score, then evaluate burst triggers."""
    try:
        updated = await run_early_trend_update(db_pool)
        logger.info("scheduled_early_trend_update_done", updated=updated)
    except Exception as exc:
        logger.error("scheduled_early_trend_update_failed", error=str(exc))
        return

    try:
        burst_count = await run_burst_job(db_pool, trigger_source="auto")
        if burst_count > 0:
            logger.info("scheduled_burst_triggered", burst_count=burst_count)
    except Exception as exc:
        logger.error("scheduled_burst_job_failed", error=str(exc))


async def _job_naver_datalab(db_pool: asyncpg.Pool) -> None:
    """Scheduled job: collect Naver DataLab search trends."""
    try:
        saved = await crawl_naver_datalab(db_pool)
        logger.info("scheduled_naver_datalab_done", saved=len(saved))
    except Exception as exc:
        logger.error("scheduled_naver_datalab_failed", error=str(exc))


async def _job_keyword_snapshot(db_pool: asyncpg.Pool) -> None:
    """Scheduled job: save keyword snapshots for active trend groups."""
    try:
        await run_keyword_snapshot(db_pool)
        logger.info("scheduled_keyword_snapshot_done")
    except Exception as exc:
        logger.error("scheduled_keyword_snapshot_failed", error=str(exc))


async def _job_keyword_review(db_pool: asyncpg.Pool) -> None:
    """Scheduled job: AI-based non-trend keyword suggestion."""
    try:
        inserted = await run_keyword_review_job(db_pool)
        logger.info("scheduled_keyword_review_done", inserted=inserted)
    except Exception as exc:
        logger.error("scheduled_keyword_review_failed", error=str(exc))


async def _job_daily_digest(db_pool: asyncpg.Pool) -> None:
    """Scheduled job: send daily Reddit question digest emails."""
    try:
        sent = await run_daily_digest(db_pool)
        logger.info("scheduled_daily_digest_done", sent=sent)
    except Exception as exc:
        logger.error("scheduled_daily_digest_failed", error=str(exc))


async def _job_quota_reset(db_pool: asyncpg.Pool) -> None:
    """Scheduled job: reset all source quotas daily."""
    try:
        await reset_all_quotas(db_pool)
        logger.info("scheduled_quota_reset_done")
    except Exception as exc:
        logger.error("scheduled_quota_reset_failed", error=str(exc))


async def _job_brand_alert(db_pool: asyncpg.Pool) -> None:
    """Scheduled job: scan brand monitors and dispatch crisis alerts."""
    try:
        alert_count = await run_brand_alert(db_pool)
        logger.info("scheduled_brand_alert_done", alert_count=alert_count)
    except Exception as exc:
        logger.error("scheduled_brand_alert_failed", error=str(exc))


async def _job_plan_expiry(db_pool: asyncpg.Pool) -> None:
    """Scheduled job: expire overdue subscriptions and downgrade to free plan."""
    try:
        expired = await run_plan_expiry(db_pool)
        logger.info("scheduled_plan_expiry_done", expired_count=expired)
    except Exception as exc:
        logger.error("scheduled_plan_expiry_failed", error=str(exc))


def create_scheduler(db_pool: asyncpg.Pool) -> AsyncIOScheduler:
    """Create and configure the APScheduler with all job definitions.

    Schedule intervals (from context/pipeline.md):
    - News crawler: every 5 minutes
    - SNS crawler: every 2 minutes
    - Community crawler: every 10 minutes
    - Quota reset: daily 00:00 UTC
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        _job_news_crawl,
        "interval",
        minutes=5,
        args=[db_pool],
        id="news_crawl",
        name="News RSS Crawler",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _job_sns_collect,
        "interval",
        minutes=2,
        args=[db_pool],
        id="sns_collect",
        name="SNS Collector",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _job_community_crawl,
        "interval",
        minutes=10,
        args=[db_pool],
        id="community_crawl",
        name="Community Crawler",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _job_early_trend_update,
        "interval",
        minutes=3,
        args=[db_pool],
        id="early_trend_update",
        name="Early Trend Score Recalculation",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _job_naver_datalab,
        "interval",
        minutes=30,
        args=[db_pool],
        id="naver_datalab",
        name="Naver DataLab Crawler",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _job_keyword_snapshot,
        "cron",
        hour="*/6",
        args=[db_pool],
        id="keyword_snapshot",
        name="Keyword Snapshot (6h)",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _job_quota_reset,
        "cron",
        hour=0,
        minute=0,
        args=[db_pool],
        id="quota_reset",
        name="Daily Quota Reset",
    )

    scheduler.add_job(
        _job_daily_digest,
        "cron",
        hour=0,
        minute=0,
        args=[db_pool],
        id="daily_digest",
        name="Daily Reddit Digest",
    )

    # F18: `hour="*/24"` raises ValueError in APScheduler (step > range 23).
    # Intent is "once a day" — use hour=1 (01:00 UTC) to offset from daily_digest.
    scheduler.add_job(
        _job_keyword_review,
        "cron",
        hour=1,
        minute=0,
        args=[db_pool],
        id="keyword_review",
        name="AI Keyword Review (daily 01:00 UTC)",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _job_brand_alert,
        "interval",
        minutes=10,
        args=[db_pool],
        id="brand_alert",
        name="Brand Crisis Alert",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _job_plan_expiry,
        "cron",
        hour=18,
        minute=0,
        args=[db_pool],
        id="plan_expiry",
        name="Plan Expiry (daily 03:00 KST)",
        max_instances=1,
        coalesce=True,
    )

    job_ids = [job.id for job in scheduler.get_jobs()]
    logger.info("scheduler_created", jobs=len(job_ids), job_ids=job_ids)
    return scheduler


async def start_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Start the scheduler."""
    try:
        scheduler.start()
        logger.info("scheduler_started")
    except Exception as exc:
        logger.error("scheduler_start_failed", error=str(exc))
        raise


async def stop_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Gracefully stop the scheduler."""
    try:
        scheduler.shutdown(wait=True)
        logger.info("scheduler_stopped")
    except Exception as exc:
        logger.error("scheduler_stop_failed", error=str(exc))
