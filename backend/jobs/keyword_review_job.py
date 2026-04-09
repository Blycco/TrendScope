"""AI 기반 비트렌드 키워드 제안 잡.

하위 점수 기사를 샘플링해 LLM에 비트렌드 여부를 물어보고,
식별 키워드를 filter_keyword 테이블에 ai_suggested 소스로 삽입한다.
(RULE 06, 07, 09)
"""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

_SAMPLE_LIMIT = 50
_SCORE_PERCENTILE_CUTOFF = 5  # 하위 5%

_REVIEW_PROMPT = (
    "다음 기사들이 트렌드 서비스에서 제외되어야 할 비트렌드(부고·광고·무관)인지 "
    "판단하고, 핵심 식별 키워드를 추출해줘. "
    'JSON 배열 형태로 키워드만 반환해줘. 예: ["부고", "서거"]'
)


async def run_keyword_review_job(pool: asyncpg.Pool) -> int:
    """하위 점수 기사에서 비트렌드 키워드를 LLM으로 추출해 DB에 저장.

    Returns:
        삽입된 키워드 수.
    """
    try:
        from backend.processor.shared.ai_config import get_ai_config
        from backend.processor.shared.ai_summarizer import summarize

        config = await get_ai_config(pool)
        if config.provider == "textrank":
            logger.info("keyword_review_job_skipped", reason="no_llm_configured")
            return 0

        # 하위 점수 기사 샘플링
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id::text, title, summary
                FROM news_group
                WHERE score IS NOT NULL
                ORDER BY score ASC
                LIMIT $1
                """,
                _SAMPLE_LIMIT,
            )

        if not rows:
            logger.info("keyword_review_job_no_rows")
            return 0

        # 기사 목록 텍스트 구성
        text_parts: list[str] = []
        for i, row in enumerate(rows, 1):
            title = row["title"] or ""
            summary = row["summary"] or ""
            text_parts.append(f"{i}. 제목: {title}\n요약: {summary}")

        text = "\n\n".join(text_parts)

        result_text, degraded = await summarize(text, _REVIEW_PROMPT, config, pool)
        if degraded or not result_text:
            logger.info("keyword_review_job_textrank_fallback")
            return 0

        # JSON 배열 파싱
        import json
        import re

        match = re.search(r"\[.*?\]", result_text, re.DOTALL)
        if not match:
            logger.warning("keyword_review_job_parse_failed", raw=result_text[:200])
            return 0

        keywords: list[str] = json.loads(match.group())
        if not isinstance(keywords, list):
            return 0

        # DB 삽입 (ai_suggested, is_active=FALSE)
        inserted = 0
        async with pool.acquire() as conn:
            for kw in keywords:
                if not isinstance(kw, str) or not kw.strip():
                    continue
                result = await conn.fetchval(
                    """
                    INSERT INTO filter_keyword
                        (keyword, category, source, is_active, confidence)
                    VALUES ($1, 'irrelevant', 'ai_suggested', FALSE, 0.7)
                    ON CONFLICT (keyword) DO NOTHING
                    RETURNING id
                    """,
                    kw.strip(),
                )
                if result:
                    inserted += 1

        logger.info("keyword_review_job_done", inserted=inserted, total=len(keywords))
        return inserted

    except Exception as exc:
        logger.error("keyword_review_job_failed", error=str(exc))
        return 0
