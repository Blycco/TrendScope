"""audit_archive — 90일 초과 audit_log를 archive 테이블로 이관."""

from __future__ import annotations

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

logger = structlog.get_logger(__name__)


async def archive_old_audit_logs(app: FastAPI) -> None:
    """90일 초과 audit_log를 audit_log_archive로 이관 후 삭제."""
    try:
        async with app.state.db_pool.acquire() as conn:
            inserted = await conn.fetchval("""
                WITH moved AS (
                    DELETE FROM audit_log
                    WHERE created_at < NOW() - INTERVAL '90 days'
                    RETURNING user_id, action, resource, resource_id,
                              ip_address, user_agent, metadata, created_at
                )
                INSERT INTO audit_log_archive
                    (user_id, action, resource, resource_id,
                     ip_address, user_agent, metadata, created_at, archived_at)
                SELECT user_id, action, resource, resource_id,
                       ip_address, user_agent, metadata, created_at, NOW()
                FROM moved
                RETURNING COUNT(*)
            """)
            logger.info("audit_log_archived", count=inserted)
    except Exception:
        logger.exception("audit_log_archive_failed")


def register_archive_job(app: FastAPI) -> AsyncIOScheduler:
    """APScheduler 등록 — 매일 새벽 3시."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        archive_old_audit_logs,
        trigger=CronTrigger(hour=3, minute=0),
        args=[app],
        id="audit_archive",
        replace_existing=True,
    )
    return scheduler
