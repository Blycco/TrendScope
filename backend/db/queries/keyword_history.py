"""키워드 히스토리 DB 쿼리."""

from __future__ import annotations

from datetime import datetime

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def save_keyword_snapshot(
    pool: asyncpg.Pool,
    group_id: str,
    keywords: list[tuple[str, int]],
) -> None:
    """keyword_snapshot 테이블에 스냅샷 INSERT.

    Args:
        pool: asyncpg connection pool
        group_id: news_group UUID (문자열)
        keywords: (keyword, frequency) 튜플 목록
    """
    if not keywords:
        return
    try:
        async with pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO keyword_snapshot (group_id, keyword, frequency) "
                "VALUES ($1::uuid, $2, $3)",
                [(group_id, kw, freq) for kw, freq in keywords],
            )
    except Exception as exc:
        logger.warning(
            "save_keyword_snapshot_failed",
            group_id=group_id,
            error=str(exc),
        )


async def fetch_keyword_history(
    pool: asyncpg.Pool,
    group_id: str,
    limit_snapshots: int = 10,
) -> list[dict]:
    """keyword_snapshot에서 group_id의 스냅샷 조회.

    snapshot_at별로 그룹핑하여 반환.

    Args:
        pool: asyncpg connection pool
        group_id: news_group UUID (문자열)
        limit_snapshots: 최신 스냅샷 수 제한

    Returns:
        [{snapshot_at: str, top_keywords: [{term, frequency}]}]
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT keyword, frequency, snapshot_at "
                "FROM keyword_snapshot "
                "WHERE group_id = $1::uuid "
                "ORDER BY snapshot_at DESC, frequency DESC",
                group_id,
            )

        # snapshot_at별 그룹핑
        snapshots: dict[datetime, list[dict]] = {}
        for row in rows:
            snap_at = row["snapshot_at"]
            snapshots.setdefault(snap_at, []).append(
                {
                    "term": row["keyword"],
                    "frequency": row["frequency"],
                }
            )

        # 최신 limit_snapshots개만
        result = []
        for snap_at in sorted(snapshots.keys(), reverse=True)[:limit_snapshots]:
            result.append(
                {
                    "snapshot_at": snap_at.isoformat(),
                    "top_keywords": snapshots[snap_at][:10],
                }
            )
        return result
    except Exception as exc:
        logger.warning(
            "fetch_keyword_history_failed",
            group_id=group_id,
            error=str(exc),
        )
        return []
