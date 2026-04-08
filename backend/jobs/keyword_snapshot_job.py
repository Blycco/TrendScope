"""6시간마다 활성 news_group의 키워드 스냅샷 저장 잡."""

from __future__ import annotations

import asyncpg
import structlog

from backend.db.queries.keyword_history import save_keyword_snapshot

logger = structlog.get_logger(__name__)

_BATCH_LIMIT = 500
_KEYWORD_LIMIT = 10


async def run_keyword_snapshot(pool: asyncpg.Pool) -> None:
    """최근 24h 내 생성된 그룹의 keywords를 keyword_snapshot 테이블에 저장.

    각 그룹의 상위 키워드를 (keyword, 1) 형태로 스냅샷 저장합니다.
    실제 빈도는 article 분석 없이 존재 여부(frequency=1)로 기록합니다.

    Args:
        pool: asyncpg connection pool
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id::text, keywords FROM news_group "
                "WHERE created_at > now() - interval '24 hours' "
                "AND keywords IS NOT NULL AND array_length(keywords, 1) > 0 "
                "ORDER BY score DESC LIMIT $1",
                _BATCH_LIMIT,
            )

        processed = 0
        errors = 0

        for row in rows:
            group_id = row["id"]
            keywords = row["keywords"] or []
            kw_pairs: list[tuple[str, int]] = [(kw, 1) for kw in keywords[:_KEYWORD_LIMIT]]
            try:
                await save_keyword_snapshot(pool, group_id, kw_pairs)
                processed += 1
            except Exception as exc:
                logger.warning(
                    "keyword_snapshot_group_failed",
                    group_id=group_id,
                    error=str(exc),
                )
                errors += 1

        logger.info(
            "keyword_snapshot_job_done",
            processed=processed,
            errors=errors,
        )
    except Exception as exc:
        logger.warning("keyword_snapshot_job_failed", error=str(exc))
