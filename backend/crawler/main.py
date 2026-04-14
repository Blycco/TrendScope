"""Crawler service entry point — runs APScheduler with periodic feed crawling."""

from __future__ import annotations

import asyncio
import os
import signal

import asyncpg
import structlog

from backend.common.heartbeat import run_heartbeat
from backend.common.logging_config import setup_logging
from backend.crawler.scheduler import create_scheduler, start_scheduler, stop_scheduler
from backend.crawler.sources.news_crawler import crawl_all as news_crawl_all
from backend.processor.shared.cache_manager import close_redis, init_redis

logger = structlog.get_logger(__name__)


async def main() -> None:
    """Boot crawler: connect DB, run initial crawl, then start scheduler loop."""
    setup_logging("crawler")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not set")

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    await init_redis(redis_url)

    db_pool = await asyncpg.create_pool(dsn=database_url, min_size=2, max_size=10)
    logger.info("crawler_db_pool_created")

    scheduler = create_scheduler(db_pool)
    await start_scheduler(scheduler)

    # 즉시 첫 뉴스 크롤링 1회 실행 (스케줄러 interval 대기 없이)
    try:
        articles = await news_crawl_all(db_pool)
        logger.info("initial_news_crawl_done", new_articles=len(articles))
    except Exception as exc:
        logger.error("initial_news_crawl_failed", error=str(exc))

    # graceful shutdown
    stop_event = asyncio.Event()

    def _handle_signal() -> None:
        logger.info("crawler_shutdown_signal_received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal)

    logger.info("crawler_running")
    heartbeat_task = asyncio.create_task(run_heartbeat(stop_event))
    await stop_event.wait()
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass

    await stop_scheduler(scheduler)
    await close_redis()
    await db_pool.close()
    logger.info("crawler_shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())
