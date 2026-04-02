"""Processor service entry point — polls unprocessed articles and runs pipeline."""

from __future__ import annotations

import asyncio
import os
import signal
from typing import Any

import asyncpg
import structlog

from backend.processor.pipeline import process_articles
from backend.processor.shared.cache_manager import close_redis, init_redis

logger = structlog.get_logger(__name__)

_POLL_INTERVAL = 30  # seconds
_BATCH_SIZE = 200


async def _fetch_unprocessed(db_pool: asyncpg.Pool) -> list[dict[str, Any]]:
    """Fetch articles without a group_id (not yet processed)."""
    rows = await db_pool.fetch(
        """
        SELECT id, url, url_hash, title, body, source, author,
               publish_time, locale
        FROM news_article
        WHERE group_id IS NULL
        ORDER BY publish_time DESC
        LIMIT $1
        """,
        _BATCH_SIZE,
    )
    return [dict(r) for r in rows]


async def _poll_loop(db_pool: asyncpg.Pool, stop_event: asyncio.Event) -> None:
    """Continuously poll for unprocessed articles and run pipeline."""
    while not stop_event.is_set():
        try:
            articles = await _fetch_unprocessed(db_pool)
            if articles:
                saved = await process_articles(articles, db_pool)
                logger.info("processor_batch_done", input=len(articles), saved=saved)
            else:
                logger.debug("processor_no_articles")
        except Exception as exc:
            logger.error("processor_poll_error", error=str(exc))

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=_POLL_INTERVAL)
        except TimeoutError:
            pass


async def main() -> None:
    """Boot processor: connect DB, start polling loop."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not set")

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    await init_redis(redis_url)

    db_pool = await asyncpg.create_pool(dsn=database_url, min_size=2, max_size=10)
    logger.info("processor_db_pool_created")

    stop_event = asyncio.Event()

    def _handle_signal() -> None:
        logger.info("processor_shutdown_signal_received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal)

    logger.info("processor_running")
    await _poll_loop(db_pool, stop_event)

    await close_redis()
    await db_pool.close()
    logger.info("processor_shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())
