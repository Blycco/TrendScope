"""027_quality_settings — 트렌드 품질 관련 admin_settings 시드."""

from __future__ import annotations

import asyncpg

VERSION = "027"
DESCRIPTION = "Add trend quality thresholds to admin_settings"

_SETTINGS = [
    ("min_article_count", 2, "트렌드 표시 최소 기사 수"),
    ("single_article_penalty", 0.3, "단건 기사 스코어 패널티 배수"),
    ("spam_min_title_length", 10, "스팸 필터 최소 제목 길이"),
]


async def up(conn: asyncpg.Connection) -> None:
    import json

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
