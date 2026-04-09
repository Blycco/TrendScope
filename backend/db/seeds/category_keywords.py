"""카테고리 분류 키워드 시드 — news_crawler.py 카테고리 재분류에 사용."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

# (keyword, category, weight)
_CATEGORY_KEYWORDS: list[tuple[str, str, float]] = [
    # ── sports ──────────────────────────────────────────────────────────
    ("축구", "sports", 1.5),
    ("야구", "sports", 1.5),
    ("농구", "sports", 1.5),
    ("배구", "sports", 1.2),
    ("선수", "sports", 1.0),
    ("감독", "sports", 1.0),
    ("경기", "sports", 1.0),
    ("리그", "sports", 1.2),
    ("골", "sports", 1.0),
    ("우승", "sports", 1.2),
    ("올림픽", "sports", 1.5),
    ("월드컵", "sports", 1.5),
    ("K리그", "sports", 2.0),
    ("MLB", "sports", 1.5),
    ("NBA", "sports", 1.5),
    ("EPL", "sports", 1.5),
    ("챔피언스리그", "sports", 1.5),
    ("국가대표", "sports", 1.3),
    ("득점", "sports", 1.0),
    ("승리", "sports", 1.0),
    # ── tech ────────────────────────────────────────────────────────────
    ("반도체", "tech", 1.5),
    ("AI", "tech", 1.5),
    ("인공지능", "tech", 1.5),
    ("스타트업", "tech", 1.2),
    ("앱", "tech", 1.0),
    ("게임", "tech", 1.0),
    ("소프트웨어", "tech", 1.2),
    ("플랫폼", "tech", 1.0),
    ("클라우드", "tech", 1.2),
    ("코딩", "tech", 1.0),
    ("데이터센터", "tech", 1.3),
    ("GPU", "tech", 1.5),
    ("LLM", "tech", 1.5),
    ("챗봇", "tech", 1.2),
    ("자율주행", "tech", 1.3),
    ("메타버스", "tech", 1.2),
    ("블록체인", "tech", 1.2),
    ("배터리", "tech", 1.2),
    ("로봇", "tech", 1.2),
    # ── economy ─────────────────────────────────────────────────────────
    ("주가", "economy", 1.5),
    ("코스피", "economy", 2.0),
    ("코스닥", "economy", 2.0),
    ("금리", "economy", 1.5),
    ("환율", "economy", 1.5),
    ("GDP", "economy", 1.5),
    ("실적", "economy", 1.2),
    ("증시", "economy", 1.5),
    ("채권", "economy", 1.3),
    ("인플레이션", "economy", 1.3),
    ("투자", "economy", 1.0),
    ("물가", "economy", 1.3),
    ("수출", "economy", 1.2),
    ("무역", "economy", 1.2),
    ("경기침체", "economy", 1.5),
    ("부동산", "economy", 1.3),
    ("금융", "economy", 1.2),
    # ── entertainment ────────────────────────────────────────────────────
    ("드라마", "entertainment", 1.5),
    ("영화", "entertainment", 1.5),
    ("아이돌", "entertainment", 1.5),
    ("배우", "entertainment", 1.2),
    ("콘서트", "entertainment", 1.3),
    ("앨범", "entertainment", 1.3),
    ("유튜브", "entertainment", 1.0),
    ("웹툰", "entertainment", 1.2),
    ("OTT", "entertainment", 1.3),
    ("뮤직비디오", "entertainment", 1.3),
    ("K팝", "entertainment", 1.5),
    ("넷플릭스", "entertainment", 1.3),
    ("시청률", "entertainment", 1.2),
    ("음원", "entertainment", 1.2),
    ("팬덤", "entertainment", 1.2),
    # ── science ──────────────────────────────────────────────────────────
    ("연구", "science", 1.0),
    ("논문", "science", 1.5),
    ("우주", "science", 1.3),
    ("실험", "science", 1.2),
    ("임상", "science", 1.5),
    ("발견", "science", 1.0),
    ("특허", "science", 1.3),
    ("NASA", "science", 1.5),
    ("백신", "science", 1.5),
    ("유전자", "science", 1.3),
    ("기후변화", "science", 1.3),
    ("탄소중립", "science", 1.2),
    # ── politics ─────────────────────────────────────────────────────────
    ("국회", "politics", 1.5),
    ("대통령", "politics", 1.5),
    ("정부", "politics", 1.2),
    ("여당", "politics", 1.3),
    ("야당", "politics", 1.3),
    ("선거", "politics", 1.5),
    ("법안", "politics", 1.2),
    ("정책", "politics", 1.0),
    ("국무총리", "politics", 1.5),
    ("장관", "politics", 1.2),
    ("외교", "politics", 1.2),
    ("UN", "politics", 1.2),
    # ── society ──────────────────────────────────────────────────────────
    ("사건", "society", 1.0),
    ("사고", "society", 1.0),
    ("범죄", "society", 1.2),
    ("교육", "society", 1.0),
    ("복지", "society", 1.0),
    ("환경", "society", 1.0),
    ("인구", "society", 1.0),
    ("고령화", "society", 1.2),
    ("저출산", "society", 1.2),
    ("육아", "society", 1.0),
]


async def seed_category_keywords(conn: asyncpg.Connection) -> None:
    """category_keyword 테이블에 시드 데이터 삽입."""
    inserted = 0

    for keyword, category, weight in _CATEGORY_KEYWORDS:
        result = await conn.fetchval(
            """
            INSERT INTO category_keyword (keyword, category, weight, locale)
            VALUES ($1, $2, $3, 'ko')
            ON CONFLICT (keyword, category) DO NOTHING
            RETURNING id
            """,
            keyword,
            category,
            weight,
        )
        if result:
            inserted += 1

    logger.info(
        "category_keywords_seeded",
        inserted=inserted,
        total=len(_CATEGORY_KEYWORDS),
    )
