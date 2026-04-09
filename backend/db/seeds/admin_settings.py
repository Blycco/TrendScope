"""Admin settings seed data — inserts default configuration rows."""

from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

_AI_CONFIG_JSON = (
    '{"provider":"textrank","model":"textrank","api_key":"",'
    '"max_tokens":512,"temperature":0.0,"fallback_provider":"textrank"}'
)

SEEDS: list[tuple[str, str, str, str]] = [
    ("payment_provider", "toss", "toss", "결제 제공자"),
    ("ai_model_primary", "gemini-flash", "gemini-flash", "AI 주 모델"),
    ("ai_model_fallback", "gpt-4o-mini", "gpt-4o-mini", "AI 폴백 모델"),
    ("quota_free_trends", "10", "10", "Free 플랜 /trends 일일 한도"),
    ("quota_pro_trends", "100", "100", "Pro 플랜 /trends 일일 한도"),
    ("early_trend_w_burst", "0.5", "0.5", "EarlyTrend 버스트 가중치"),
    ("early_trend_w_velocity", "0.3", "0.3", "EarlyTrend 속도 가중치"),
    ("early_trend_w_diversity", "0.2", "0.2", "EarlyTrend 다양성 가중치"),
    ("ai.config", _AI_CONFIG_JSON, _AI_CONFIG_JSON, "AI summarization provider config"),
    ("burst_threshold", "0.75", "0.75", "Burst 트리거 early_trend_score 임계값"),
    ("burst_cooldown_hours", "2", "2", "같은 트렌드 Burst 재트리거 쿨다운(시간)"),
    # ── 클러스터링 파라미터 ────────────────────────────────────────────────
    ("cluster.cosine_weight", "0.35", "0.35", "클러스터 코사인 유사도 가중치"),
    ("cluster.jaccard_weight", "0.40", "0.40", "클러스터 Jaccard 키워드 가중치"),
    ("cluster.temporal_weight", "0.05", "0.05", "클러스터 시간 근접 가중치"),
    ("cluster.source_weight", "0.20", "0.20", "클러스터 소스 일치 가중치"),
    ("cluster.jaccard_early_filter", "0.25", "0.25", "Jaccard 조기 필터 임계값"),
    ("cluster.threshold", "0.65", "0.65", "클러스터 합산 유사도 임계값"),
    ("cluster.outlier_sigma", "0.7", "0.7", "클러스터 이상치 제거 시그마"),
    ("cluster.temporal_decay_hours", "24.0", "24.0", "시간 유사도 감쇠 시간(시간)"),
    ("cluster.louvain_threshold", "0.70", "0.70", "Louvain 커뮤니티 감지 임계값"),
    # ── 점수 가중치 (합계 100) ────────────────────────────────────────────
    ("score.weight_freshness", "25", "25", "점수: 신선도 가중치"),
    ("score.weight_burst", "25", "25", "점수: 버스트 가중치"),
    ("score.weight_article_count", "15", "15", "점수: 기사 수 가중치"),
    ("score.weight_source_diversity", "12", "12", "점수: 소스 다양성 가중치"),
    ("score.weight_social", "10", "10", "점수: 소셜 시그널 가중치"),
    ("score.weight_keyword", "8", "8", "점수: 키워드 중요도 가중치"),
    ("score.weight_velocity", "5", "5", "점수: 속도(velocity) 가중치"),
    # ── 신선도 감쇠 lambda ────────────────────────────────────────────────
    ("decay.breaking", "0.10", "0.10", "신선도 감쇠: breaking"),
    ("decay.politics", "0.04", "0.04", "신선도 감쇠: politics"),
    ("decay.it", "0.02", "0.02", "신선도 감쇠: it"),
    ("decay.default", "0.05", "0.05", "신선도 감쇠: default"),
    # ── 스팸 필터 파라미터 ────────────────────────────────────────────────
    ("spam.url_ratio_threshold", "0.3", "0.3", "스팸: URL 비율 임계값"),
    ("spam.keyword_threshold", "3", "3", "스팸: 스팸키워드 개수 임계값"),
    ("spam.min_content_length", "20", "20", "스팸: 최소 본문 길이"),
    ("spam.non_trend_min_hits", "2", "2", "비트렌드: 키워드 최소 매칭 수"),
    # ── 키워드 추출 파라미터 ──────────────────────────────────────────────
    ("keyword.title_boost", "2.0", "2.0", "키워드: 제목 토큰 가중치"),
    ("keyword.body_max_chars", "500", "500", "키워드: 본문 최대 처리 글자 수"),
    ("keyword.top_k", "10", "10", "키워드: 추출 상위 K개"),
]


async def run_seed(pool: asyncpg.Pool) -> int:
    """Insert admin_settings seed rows. Skips rows that already exist.

    Returns the number of rows inserted.
    """
    try:
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO admin_settings (key, value, default_value, description)
                VALUES ($1, to_jsonb($2::text), to_jsonb($3::text), $4)
                ON CONFLICT (key) DO NOTHING
                """,
                SEEDS,
            )
        logger.info("admin_settings_seed_complete", seeds=len(SEEDS))
        return len(SEEDS)
    except Exception as exc:
        logger.error("admin_settings_seed_failed", error=str(exc))
        raise
