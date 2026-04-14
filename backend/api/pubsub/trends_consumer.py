"""Long-running consumer for the `trends:new` Redis pub/sub channel.

On each new group_id:
  1. Match against notification_keyword (alert_surge=TRUE) and log alerts.
  2. Invalidate the `feed:*` cache so subsequent /trends queries refresh.
"""

from __future__ import annotations

import asyncio

import asyncpg
import structlog

from backend.db.queries.trends import fetch_trend_detail
from backend.processor.shared.cache_manager import (
    get_pubsub_redis,
    invalidate_feed_cache,
)

logger = structlog.get_logger(__name__)

_CHANNEL = "trends:new"
_RECONNECT_DELAY = 5.0


async def _match_keyword_alerts(
    pool: asyncpg.Pool,
    keywords: list[str],
) -> list[asyncpg.Record]:
    """Return notification_keyword rows whose keyword matches (case-insensitive)."""
    if not keywords:
        return []
    lowered = [k.lower() for k in keywords if k]
    if not lowered:
        return []
    try:
        async with pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT id::text, user_id::text, keyword
                FROM notification_keyword
                WHERE alert_surge = TRUE
                  AND LOWER(keyword) = ANY($1::text[])
                """,
                lowered,
            )
    except Exception as exc:
        logger.warning("keyword_alert_match_failed", error=str(exc))
        return []


async def _handle_message(pool: asyncpg.Pool, group_id: str) -> None:
    """Process a single `trends:new` message."""
    try:
        detail = await fetch_trend_detail(pool, group_id=group_id)
    except Exception as exc:
        logger.warning("trends_consumer_fetch_failed", group_id=group_id, error=str(exc))
        return

    if not detail:
        logger.debug("trends_consumer_group_not_found", group_id=group_id)
        return

    group = detail["group"]
    raw_keywords = group.get("keywords") if isinstance(group, dict) else group["keywords"]
    keywords: list[str] = list(raw_keywords or [])

    matches = await _match_keyword_alerts(pool, keywords)
    for row in matches:
        logger.info(
            "keyword_alert_triggered",
            user_id=row["user_id"],
            keyword=row["keyword"],
            group_id=group_id,
        )

    await invalidate_feed_cache()


async def run_trends_consumer(pool: asyncpg.Pool) -> None:
    """Subscribe to `trends:new` forever. Cancels cleanly on task.cancel()."""
    while True:
        pubsub = None
        try:
            redis = get_pubsub_redis()
            pubsub = redis.pubsub()
            await pubsub.subscribe(_CHANNEL)
            logger.info("trends_consumer_subscribed", channel=_CHANNEL)

            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=30.0,
                )
                if not message or message.get("type") != "message":
                    continue
                group_id = message["data"]
                if not isinstance(group_id, str) or not group_id:
                    logger.warning("trends_consumer_bad_payload", payload=repr(group_id))
                    continue
                try:
                    await _handle_message(pool, group_id)
                except Exception as exc:
                    logger.warning(
                        "trends_consumer_handle_failed",
                        group_id=group_id,
                        error=str(exc),
                    )
        except asyncio.CancelledError:
            logger.info("trends_consumer_cancelled")
            raise
        except Exception as exc:
            logger.warning("trends_consumer_loop_error", error=str(exc))
            await asyncio.sleep(_RECONNECT_DELAY)
        finally:
            if pubsub is not None:
                try:
                    await pubsub.unsubscribe(_CHANNEL)
                    await pubsub.aclose()
                except Exception as cleanup_exc:
                    logger.debug("trends_consumer_cleanup_error", error=str(cleanup_exc))
