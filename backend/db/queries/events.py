"""DB query layer for user_action_log (events). (RULE 02: asyncpg $1,$2)"""

from __future__ import annotations

import json
from typing import Any

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


async def get_behavior_stats(
    pool: asyncpg.Pool,
    *,
    user_id: str,
    days: int = 30,
) -> dict[str, Any]:
    """Aggregate user behavior from user_action_log for the last N days.

    Returns category click counts, total events, and top item types.
    """
    try:
        async with pool.acquire() as conn:
            # Category interest from trend/news clicks (meta->>'category')
            category_rows = await conn.fetch(
                """
                SELECT meta->>'category' AS category, COUNT(*) AS cnt
                FROM user_action_log
                WHERE user_id = $1::uuid
                  AND action IN ('click', 'page_view', 'scrape')
                  AND meta->>'category' IS NOT NULL
                  AND created_at > NOW() - make_interval(days => $2)
                GROUP BY meta->>'category'
                ORDER BY cnt DESC
                """,
                user_id,
                days,
            )

            # Total event count
            total_row = await conn.fetchrow(
                """
                SELECT COUNT(*) AS total
                FROM user_action_log
                WHERE user_id = $1::uuid
                  AND created_at > NOW() - make_interval(days => $2)
                """,
                user_id,
                days,
            )

            # Top actions breakdown
            action_rows = await conn.fetch(
                """
                SELECT action, COUNT(*) AS cnt
                FROM user_action_log
                WHERE user_id = $1::uuid
                  AND created_at > NOW() - make_interval(days => $2)
                GROUP BY action
                ORDER BY cnt DESC
                LIMIT 10
                """,
                user_id,
                days,
            )

        category_counts = {row["category"]: row["cnt"] for row in category_rows}
        total_events = total_row["total"] if total_row else 0
        action_counts = {row["action"]: row["cnt"] for row in action_rows}

        return {
            "category_counts": category_counts,
            "total_events": total_events,
            "action_counts": action_counts,
        }
    except Exception as exc:
        logger.error("get_behavior_stats_failed", user_id=user_id, error=str(exc))
        raise
