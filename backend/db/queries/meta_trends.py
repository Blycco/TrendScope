"""메타 트렌드 DB 쿼리."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def fetch_groups_for_meta(
    pool: asyncpg.Pool,
    *,
    locale: str | None = None,
    limit: int = 200,
    min_score: float = 5.0,
) -> list[dict]:
    """메타 클러스터링용 news_group 조회.

    Args:
        pool: asyncpg connection pool
        locale: 언어 필터 (None이면 전체)
        limit: 최대 조회 수
        min_score: 최소 score 임계값

    Returns:
        group 딕셔너리 목록 (id, title, category, keywords, score)
    """
    try:
        async with pool.acquire() as conn:
            if locale:
                rows = await conn.fetch(
                    "SELECT id::text, title, category, keywords, score "
                    "FROM news_group "
                    "WHERE locale = $1 AND score >= $2 "
                    "ORDER BY score DESC LIMIT $3",
                    locale,
                    min_score,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    "SELECT id::text, title, category, keywords, score "
                    "FROM news_group "
                    "WHERE score >= $1 "
                    "ORDER BY score DESC LIMIT $2",
                    min_score,
                    limit,
                )
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.warning("fetch_groups_for_meta_failed", error=str(exc))
        return []
