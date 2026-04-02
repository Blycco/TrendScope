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
