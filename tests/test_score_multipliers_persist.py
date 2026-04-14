"""Tests for stage_save persisting cross_platform_multiplier / external_trend_boost."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.processor.stages import save as save_stage


def _make_cluster(
    *,
    cross_platform_multiplier: float = 1.25,
    external_trend_boost: float = 1.1,
    growth_type: str = "spike",
) -> dict:
    return {
        "category": "it",
        "locale": "ko",
        "title": "AI 급등",
        "summary": "요약",
        "score": 85.5,
        "early_trend_score": 0.7,
        "keywords": ["AI", "LLM"],
        "burst_score": 0.6,
        "cross_platform_multiplier": cross_platform_multiplier,
        "external_trend_boost": external_trend_boost,
        "growth_type": growth_type,
        "articles": [{"url_hash": "h1"}],
    }


class TestStageSaveMultipliers:
    @pytest.mark.asyncio
    async def test_batch_insert_includes_multipliers(self) -> None:
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[{"id": "gid-1"}])
        conn.executemany = AsyncMock()

        tx = MagicMock()
        tx.__aenter__ = AsyncMock(return_value=None)
        tx.__aexit__ = AsyncMock(return_value=None)
        conn.transaction = MagicMock(return_value=tx)

        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_cm)

        cluster = _make_cluster(cross_platform_multiplier=1.25, external_trend_boost=1.1)
        with patch.object(save_stage, "publish", AsyncMock()):
            saved = await save_stage.stage_save([cluster], pool)

        assert saved == 1
        conn.fetch.assert_awaited_once()
        sql, *args = conn.fetch.await_args.args
        assert "cross_platform_multiplier" in sql
        assert "external_trend_boost" in sql
        assert "growth_type" in sql
        # args positions 8,9,10 correspond to $9,$10,$11 = multiplier/boost/growth_type lists
        assert args[8] == [1.25]
        assert args[9] == [1.1]
        assert args[10] == ["spike"]

    @pytest.mark.asyncio
    async def test_fallback_insert_includes_multipliers(self) -> None:
        pool = MagicMock()
        pool.fetchval = AsyncMock(return_value="gid-2")
        pool.execute = AsyncMock()

        cluster = _make_cluster(cross_platform_multiplier=0.9, external_trend_boost=1.2)
        saved = await save_stage._save_individually([cluster], pool)

        assert saved == 1
        pool.fetchval.assert_awaited_once()
        sql, *args = pool.fetchval.await_args.args
        assert "cross_platform_multiplier" in sql
        assert "external_trend_boost" in sql
        assert "growth_type" in sql
        # $1..$11 = category, locale, title, summary, score, early, kw, burst, mult, boost, growth
        assert args[8] == 0.9
        assert args[9] == 1.2
        assert args[10] == "spike"

    @pytest.mark.asyncio
    async def test_missing_keys_default_to_one(self) -> None:
        """Older callers without multiplier keys should default to 1.0 (neutral)."""
        pool = MagicMock()
        pool.fetchval = AsyncMock(return_value="gid-3")
        pool.execute = AsyncMock()

        cluster = _make_cluster()
        cluster.pop("cross_platform_multiplier")
        cluster.pop("external_trend_boost")
        cluster.pop("growth_type")

        await save_stage._save_individually([cluster], pool)

        args = pool.fetchval.await_args.args
        assert args[-3] == 1.0
        assert args[-2] == 1.0
        assert args[-1] == "unknown"
