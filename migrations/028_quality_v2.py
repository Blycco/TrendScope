"""028_quality_v2 — 구간별 기사 수 페널티 설정 + 기존 데이터 소급 보정."""

from __future__ import annotations

import asyncpg

VERSION = "028"
DESCRIPTION = "Graduated article count penalty settings and retroactive score correction"

_SETTINGS = [
    ("article_count_penalty_1", 0.3, "1건 기사 클러스터 페널티 배수"),
    ("article_count_penalty_2", 0.5, "2건 기사 클러스터 페널티 배수"),
    ("article_count_penalty_3", 0.7, "3건 기사 클러스터 페널티 배수"),
    ("article_count_penalty_4", 0.85, "4건 기사 클러스터 페널티 배수"),
    ("early_trend_min_score", 0.4, "얼리 트렌드 배지 최소 점수"),
    ("early_trend_min_sources", 2, "얼리 트렌드 최소 소스 수"),
    ("burst_min_series_points", 5, "Burst 탐지 최소 시계열 포인트"),
]


async def up(conn: asyncpg.Connection) -> None:
    import json

    # 1) Seed admin_settings
    for key, value, description in _SETTINGS:
        json_value = json.dumps(value)
        await conn.execute(
            """
            INSERT INTO admin_settings (key, value, default_value, description)
            VALUES ($1, $2::jsonb, $3::jsonb, $4)
            ON CONFLICT (key) DO NOTHING
            """,
            key,
            json_value,
            json_value,
            description,
        )

    # 2) Retroactive score correction for 2~4 article clusters
    # Apply graduated penalty to existing news_group rows
    for count, penalty in [(2, 0.5), (3, 0.7), (4, 0.85)]:
        await conn.execute(
            """
            UPDATE news_group ng
            SET score = ROUND((score * $1)::numeric, 2)
            WHERE (
                SELECT COUNT(*) FROM news_article
                WHERE group_id = ng.id
            ) = $2
            AND score > 0
            """,
            penalty,
            count,
        )

    # 3) Reset early_trend_score to 0 for single-source clusters
    await conn.execute(
        """
        UPDATE news_group ng
        SET early_trend_score = 0.0
        WHERE (
            SELECT COUNT(DISTINCT source) FROM news_article
            WHERE group_id = ng.id
        ) < 2
        AND early_trend_score > 0
        """
    )
