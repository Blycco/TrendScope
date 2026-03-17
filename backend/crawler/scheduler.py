"""APScheduler job definitions for TrendScope crawlers."""

from __future__ import annotations

import asyncpg
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.crawler.quota_guard import reset_all_quotas
from backend.crawler.sources.community_crawler import crawl_all as community_crawl_all
from backend.crawler.sources.news_crawler import crawl_all as news_crawl_all
from backend.crawler.sources.sns_crawler import collect_all as sns_collect_all

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


async def _job_quota_reset(db_pool: asyncpg.Pool) -> None:
    """Scheduled job: reset all source quotas daily."""
    try:
        await reset_all_quotas(db_pool)
        logger.info("scheduled_quota_reset_done")
    except Exception as exc:
        logger.error("scheduled_quota_reset_failed", error=str(exc))


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
        _job_quota_reset,
        "cron",
        hour=0,
        minute=0,
        args=[db_pool],
        id="quota_reset",
        name="Daily Quota Reset",
    )

    logger.info("scheduler_created", jobs=len(scheduler.get_jobs()))
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
