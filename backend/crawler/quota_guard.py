"""Quota guard — check/increment source quotas against source_config table. (RULE 09)"""

from __future__ import annotations

import asyncpg
import structlog

from backend.common.metrics import SOURCE_QUOTA_RATIO

logger = structlog.get_logger(__name__)


async def check_quota(source_name: str, db_pool: asyncpg.Pool) -> bool:
    """Return True if source is active and under quota limit.

    Rules (from context/pipeline.md):
    - If source disabled → False
    - If quota_limit == 0 → unlimited (True)
    - If quota_used >= quota_limit → False
    """
    try:
        row = await db_pool.fetchrow(
            "SELECT is_active, quota_limit, quota_used "
            "FROM source_config WHERE source_name = $1",
            source_name,
        )
        if row is None:
            logger.warning("quota_source_not_found", source=source_name)
            return False

        if not row["is_active"]:
            logger.info("quota_source_disabled", source=source_name)
            return False

        limit: int = row["quota_limit"]
        used: int = row["quota_used"]

        if limit == 0:
            return True

        SOURCE_QUOTA_RATIO.labels(source=source_name).set(used / limit)

        if used >= limit:
            logger.warning(
                "quota_exceeded",
                source=source_name,
                used=used,
                limit=limit,
            )
            return False

        return True
    except Exception as exc:
        logger.error("quota_check_failed", source=source_name, error=str(exc))
        return False


async def increment_quota(source_name: str, db_pool: asyncpg.Pool) -> None:
    """Increment quota_used by 1 for the given source."""
    try:
        await db_pool.execute(
            "UPDATE source_config SET quota_used = quota_used + 1, "
            "updated_at = now() WHERE source_name = $1",
            source_name,
        )
        logger.debug("quota_incremented", source=source_name)
    except Exception as exc:
        logger.error("quota_increment_failed", source=source_name, error=str(exc))


async def reset_all_quotas(db_pool: asyncpg.Pool) -> None:
    """Reset quota_used to 0 for all sources. Called by daily cron."""
    try:
        result = await db_pool.execute(
            "UPDATE source_config SET quota_used = 0, updated_at = now()"
        )
        logger.info("quota_reset_all", result=result)
    except Exception as exc:
        logger.error("quota_reset_failed", error=str(exc))
