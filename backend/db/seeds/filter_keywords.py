"""필터 키워드 시드 — spam_filter.py 하드코딩에서 이전 + 부고/비트렌드 신규 추가."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

# (keyword, category, confidence)
_FILTER_KEYWORDS: list[tuple[str, str, float]] = [
    # 광고/홍보 (기존 _SPAM_KEYWORDS에서 이전)
    ("광고", "ad", 1.0),
    ("홍보", "ad", 1.0),
    ("무료", "ad", 0.8),
    ("할인", "ad", 0.8),
    ("쿠폰", "ad", 0.9),
    ("이벤트", "ad", 0.7),
    ("당첨", "ad", 0.9),
    ("대출", "ad", 0.9),
    ("카지노", "gambling", 1.0),
    ("도박", "gambling", 1.0),
    ("슬롯", "gambling", 1.0),
    ("바카라", "gambling", 1.0),
    ("토토", "gambling", 1.0),
    ("베팅", "gambling", 0.9),
    ("성인", "adult", 0.9),
    ("만남", "adult", 0.8),
    ("채팅", "adult", 0.7),
    ("부업", "ad", 0.9),
    ("재택", "ad", 0.7),
    ("수익", "ad", 0.7),
    ("클릭", "ad", 0.8),
    ("지금바로", "ad", 0.9),
    ("한정", "ad", 0.7),
    # 영어 스팸 (기존 이전)
    ("buy now", "ad", 1.0),
    ("free money", "ad", 1.0),
    ("click here", "ad", 1.0),
    ("limited offer", "ad", 0.9),
    ("casino", "gambling", 1.0),
    ("gambling", "gambling", 1.0),
    ("lottery", "gambling", 0.9),
    ("prize", "ad", 0.8),
    ("viagra", "adult", 1.0),
    ("cialis", "adult", 1.0),
    ("weight loss", "ad", 0.8),
    # 부고/비트렌드 (신규 — 이게 핵심)
    ("부고", "obituary", 1.0),
    ("訃告", "obituary", 1.0),
    ("서거", "obituary", 1.0),
    ("별세", "obituary", 1.0),
    ("추도", "obituary", 1.0),
    ("조문", "obituary", 0.9),
    ("영결식", "obituary", 1.0),
    ("빈소", "obituary", 1.0),
    ("장례식", "obituary", 1.0),
    ("사망진단", "obituary", 1.0),
    ("부음", "obituary", 1.0),
    ("향년", "obituary", 1.0),
    ("작고", "obituary", 1.0),
    ("타계", "obituary", 1.0),
    ("유족", "obituary", 0.9),
    ("발인", "obituary", 1.0),
]


async def seed_filter_keywords(conn: asyncpg.Connection) -> None:
    """filter_keyword 테이블에 시드 데이터 삽입."""
    inserted = 0

    for keyword, category, confidence in _FILTER_KEYWORDS:
        result = await conn.fetchval(
            """
            INSERT INTO filter_keyword (keyword, category, source, confidence)
            VALUES ($1, $2, 'system', $3)
            ON CONFLICT (keyword) DO NOTHING
            RETURNING id
            """,
            keyword,
            category,
            confidence,
        )
        if result:
            inserted += 1

    logger.info(
        "filter_keywords_seeded",
        inserted=inserted,
        total=len(_FILTER_KEYWORDS),
    )
