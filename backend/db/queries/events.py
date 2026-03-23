"""DB query layer for user_action_log (events). (RULE 02: asyncpg $1,$2)"""

from __future__ import annotations

import json

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def batch_insert_events(
    pool: asyncpg.Pool,
    *,
    user_id: str,
    events: list[dict],
) -> int:
    """Insert a batch of user action events. Returns the count inserted.

    Each event dict must have ``action``; optional: ``item_type``, ``item_id``,
    ``dwell_ms``, ``meta``.
    """
    if not events:
        return 0

    try:
        async with pool.acquire() as conn:
            rows = [
                (
                    user_id,
                    evt["action"],
                    evt.get("item_type"),
                    evt.get("item_id"),
                    evt.get("dwell_ms"),
                    json.dumps(evt.get("meta", {})),
                )
                for evt in events
            ]
            await conn.executemany(
                """
                INSERT INTO user_action_log
                    (user_id, action, item_type, item_id, dwell_ms, meta)
                VALUES ($1::uuid, $2, $3, $4::uuid, $5, $6::jsonb)
                """,
                rows,
            )
            return len(rows)
    except Exception as exc:
        logger.error("batch_insert_events_failed", user_id=user_id, error=str(exc))
        raise
