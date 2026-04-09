"""불용어 시드 데이터 — keyword_extractor.py 하드코딩에서 이전 + 신규 추가."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

# 한국어 불용어 — 기존 _KOREAN_STOP_WORDS 전체 + 신규
_KO_WORDS: list[str] = [
    # 조사/어미/접속사
    "것이",
    "하는",
    "있는",
    "하고",
    "에서",
    "으로",
    "이다",
    "했다",
    "되는",
    "하며",
    "그리고",
    "또한",
    "이를",
    "통해",
    "이번",
    "대한",
    "위해",
    "관련",
    "따르면",
    "밝혔다",
    "전했다",
    # 뉴스 빈출 무의미 단어
    "것으로",
    "지난",
    "올해",
    "오늘",
    "내년",
    "최근",
    "현재",
    "이후",
    "가운데",
    "사이",
    "가량",
    "정도",
    "이상",
    "미만",
    "대비",
    "전년",
    "분기",
    "한편",
    "이날",
    # 매체/기자
    "기자",
    "특파원",
    "뉴스",
    "연합뉴스",
    "한겨레",
    "매일경제",
    "조선일보",
    "중앙일보",
    "동아일보",
    "한국경제",
    "머니투데이",
    "아시아경제",
    "헤럴드경제",
    # 월/분기 (신규 — "12월"만 같은 이유로 클러스터링 방지)
    "1월",
    "2월",
    "3월",
    "4월",
    "5월",
    "6월",
    "7월",
    "8월",
    "9월",
    "10월",
    "11월",
    "12월",
    "1분기",
    "2분기",
    "3분기",
    "4분기",
    "상반기",
    "하반기",
    # 시간 표현 (신규)
    "연도",
    "기간",
    "당일",
    "전날",
    "다음날",
    "내달",
    "다음달",
    # 뉴스 보일러플레이트 (신규)
    "보도",
    "취재",
    "단독",
    "속보",
    "긴급",
    "업데이트",
    "확인",
    "발표",
    "입장",
    "해명",
    "논평",
    "공식",
    "관계자",
    "측에따르면",
    # 수량/비율 (신규)
    "억원",
    "조원",
    "만원",
    "달러",
    "퍼센트",
    "배증",
    "감소",
    "증가",
]

# 영어 불용어 — 기존 _STOP_WORDS 전체
_EN_WORDS: list[str] = [
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "shall",
    "can",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "he",
    "she",
    "they",
    "we",
    "you",
    "i",
    "am",
    "from",
    "by",
    "about",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "not",
    "no",
    "nor",
    "so",
    "yet",
    "both",
    "either",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "than",
    "too",
    "very",
    "just",
    "only",
    "also",
    "what",
    "which",
    "who",
    "whom",
    "whose",
    "when",
    "where",
    "why",
    "how",
    "all",
    "any",
    "because",
    "if",
    "while",
    "although",
    "though",
    "since",
    "until",
    "unless",
    "therefore",
    "however",
    "additionally",
    "moreover",
    "furthermore",
    "consequently",
    "nevertheless",
    "also",
    "its",
    "his",
    "her",
]


async def seed_stopwords(conn: asyncpg.Connection) -> None:
    """stopword 테이블에 시드 데이터 삽입."""
    ko_count = 0
    en_count = 0

    for word in _KO_WORDS:
        result = await conn.fetchval(
            """
            INSERT INTO stopword (word, locale, source)
            VALUES ($1, 'ko', 'system')
            ON CONFLICT (word, locale) DO NOTHING
            RETURNING id
            """,
            word,
        )
        if result:
            ko_count += 1

    for word in _EN_WORDS:
        result = await conn.fetchval(
            """
            INSERT INTO stopword (word, locale, source)
            VALUES ($1, 'en', 'system')
            ON CONFLICT (word, locale) DO NOTHING
            RETURNING id
            """,
            word,
        )
        if result:
            en_count += 1

    logger.info(
        "stopwords_seeded",
        ko_inserted=ko_count,
        en_inserted=en_count,
        ko_total=len(_KO_WORDS),
        en_total=len(_EN_WORDS),
    )
