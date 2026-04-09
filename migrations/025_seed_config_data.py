"""025_seed_config_data — stopword, filter_keyword, category_keyword, admin_settings 시드."""

from __future__ import annotations

import asyncpg
import structlog
from backend.db.seeds.category_keywords import seed_category_keywords
from backend.db.seeds.filter_keywords import seed_filter_keywords
from backend.db.seeds.stopwords import seed_stopwords

logger = structlog.get_logger(__name__)

VERSION = "025"
DESCRIPTION = "Seed stopwords, filter_keywords, category_keywords, admin_settings algorithm params"

# admin_settings 추가 시드 (클러스터링·점수·스팸·키워드 파라미터)
_ADMIN_SETTINGS: list[tuple[str, str, str, str]] = [
    # 클러스터링
    ("cluster.cosine_weight",        "0.35", "0.35", "클러스터 코사인 유사도 가중치"),
    ("cluster.jaccard_weight",       "0.40", "0.40", "클러스터 Jaccard 키워드 가중치"),
    ("cluster.temporal_weight",      "0.05", "0.05", "클러스터 시간 근접 가중치"),
    ("cluster.source_weight",        "0.20", "0.20", "클러스터 소스 일치 가중치"),
    ("cluster.jaccard_early_filter", "0.25", "0.25", "Jaccard 조기 필터 임계값"),
    ("cluster.threshold",            "0.65", "0.65", "클러스터 합산 유사도 임계값"),
    ("cluster.outlier_sigma",        "0.7",  "0.7",  "클러스터 이상치 제거 시그마"),
    ("cluster.temporal_decay_hours", "24.0", "24.0", "시간 유사도 감쇠 시간(시간)"),
    ("cluster.louvain_threshold",    "0.70", "0.70", "Louvain 커뮤니티 감지 임계값"),
    # 점수 가중치 (합계 100)
    ("score.weight_freshness",        "25", "25", "점수: 신선도 가중치"),
    ("score.weight_burst",            "25", "25", "점수: 버스트 가중치"),
    ("score.weight_article_count",    "15", "15", "점수: 기사 수 가중치"),
    ("score.weight_source_diversity", "12", "12", "점수: 소스 다양성 가중치"),
    ("score.weight_social",           "10", "10", "점수: 소셜 시그널 가중치"),
    ("score.weight_keyword",           "8",  "8", "점수: 키워드 중요도 가중치"),
    ("score.weight_velocity",          "5",  "5", "점수: 속도(velocity) 가중치"),
    # 신선도 감쇠 lambda
    ("decay.breaking", "0.10", "0.10", "신선도 감쇠: breaking"),
    ("decay.politics", "0.04", "0.04", "신선도 감쇠: politics"),
    ("decay.it",       "0.02", "0.02", "신선도 감쇠: it"),
    ("decay.default",  "0.05", "0.05", "신선도 감쇠: default"),
    # 스팸 필터 파라미터
    ("spam.url_ratio_threshold", "0.3", "0.3", "스팸: URL 비율 임계값"),
    ("spam.keyword_threshold",   "3",   "3",   "스팸: 스팸키워드 개수 임계값"),
    ("spam.min_content_length",  "20",  "20",  "스팸: 최소 본문 길이"),
    ("spam.non_trend_min_hits",  "2",   "2",   "비트렌드: 키워드 최소 매칭 수"),
    # 키워드 추출 파라미터
    ("keyword.title_boost",    "2.0", "2.0", "키워드: 제목 토큰 가중치"),
    ("keyword.body_max_chars", "500", "500", "키워드: 본문 최대 처리 글자 수"),
    ("keyword.top_k",          "10",  "10",  "키워드: 추출 상위 K개"),
]


async def up(conn: asyncpg.Connection) -> None:
    """Seed all config tables and admin_settings algorithm params."""
    await seed_stopwords(conn)
    await seed_filter_keywords(conn)
    await seed_category_keywords(conn)

    inserted = 0
    for key, value, default_value, description in _ADMIN_SETTINGS:
        result = await conn.fetchval(
            """
            INSERT INTO admin_settings (key, value, default_value, description)
            VALUES ($1, to_jsonb($2::text), to_jsonb($3::text), $4)
            ON CONFLICT (key) DO NOTHING
            RETURNING key
            """,
            key,
            value,
            default_value,
            description,
        )
        if result:
            inserted += 1

    logger.info(
        "migration_025_complete",
        admin_settings_inserted=inserted,
        admin_settings_total=len(_ADMIN_SETTINGS),
    )


async def down(conn: asyncpg.Connection) -> None:
    """Remove seeded config data."""
    # admin_settings 파라미터 삭제
    keys = [row[0] for row in _ADMIN_SETTINGS]
    await conn.execute(
        "DELETE FROM admin_settings WHERE key = ANY($1::text[])",
        keys,
    )
    # 시드 데이터 삭제 (source='system'만)
    await conn.execute("DELETE FROM stopword WHERE source = 'system'")
    await conn.execute("DELETE FROM filter_keyword WHERE source = 'system'")
    await conn.execute("DELETE FROM category_keyword WHERE source = 'system'")
    logger.info("migration_025_reverted")
