"""Tests for ActionInsightEngine (action_insight.py).

Coverage targets:
- generate(): cache hit, cache miss + AI success, cache miss + JSON parse failure
- _build_prompt(): all 4 roles + unknown role fallback
- _persist(): success path, error path (best-effort, no raise)
- _fallback_content(): all 4 roles
- anti-hallucination URL filtering
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.api.schemas.insights import InsightRequest
from backend.processor.algorithms.action_insight import ActionInsightEngine, SourceItem
from backend.processor.shared.ai_config import AIConfig
from pydantic import SecretStr

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_ai_config() -> AIConfig:
    return AIConfig(
        provider="textrank",
        model="textrank",
        api_key=SecretStr(""),
        max_tokens=512,
        temperature=0.0,
        fallback_provider="textrank",
    )


def _make_pool() -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool


def _make_sources() -> list[SourceItem]:
    return [
        SourceItem(
            title="AI 트렌드 급상승",
            body="인공지능 관련 검색량이 급격히 증가하고 있습니다.",
            url="https://example.com/article/1",
            source_type="news",
        ),
        SourceItem(
            title="SNS 반응",
            body="소셜미디어에서 AI 관련 게시물이 폭발적으로 증가.",
            url="https://example.com/sns/2",
            source_type="sns",
        ),
    ]


def _make_req(role: str = "marketer") -> InsightRequest:
    return InsightRequest(keyword="AI 트렌드", role=role, locale="ko")


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_marketer_prompt_contains_ad_opportunities(self) -> None:
        engine = ActionInsightEngine(_make_pool(), _make_ai_config())
        prompt = engine._build_prompt("marketer")
        assert "ad_opportunities" in prompt
        assert "JSON" in prompt

    def test_creator_prompt_contains_title_drafts(self) -> None:
        engine = ActionInsightEngine(_make_pool(), _make_ai_config())
        prompt = engine._build_prompt("creator")
        assert "title_drafts" in prompt
        assert "seo_keywords" in prompt

    def test_owner_prompt_contains_consumer_reactions(self) -> None:
        engine = ActionInsightEngine(_make_pool(), _make_ai_config())
        prompt = engine._build_prompt("owner")
        assert "consumer_reactions" in prompt
        assert "market_ops" in prompt

    def test_general_prompt_contains_sns_drafts(self) -> None:
        engine = ActionInsightEngine(_make_pool(), _make_ai_config())
        prompt = engine._build_prompt("general")
        assert "sns_drafts" in prompt
        assert "engagement_methods" in prompt

    def test_unknown_role_falls_back_to_general(self) -> None:
        engine = ActionInsightEngine(_make_pool(), _make_ai_config())
        prompt = engine._build_prompt("unknown_role")
        # Should return general prompt
        assert "sns_drafts" in prompt


# ---------------------------------------------------------------------------
# _fallback_content
# ---------------------------------------------------------------------------


class TestFallbackContent:
    def test_marketer_fallback(self) -> None:
        engine = ActionInsightEngine(_make_pool(), _make_ai_config())
        sources = _make_sources()
        result = engine._fallback_content("marketer", sources)
        assert "ad_opportunities" in result
        assert "source_urls" in result
        assert len(result["source_urls"]) <= 3

    def test_creator_fallback(self) -> None:
        engine = ActionInsightEngine(_make_pool(), _make_ai_config())
        result = engine._fallback_content("creator", _make_sources())
        assert "title_drafts" in result
        assert "timing" in result
        assert "seo_keywords" in result

    def test_owner_fallback(self) -> None:
        engine = ActionInsightEngine(_make_pool(), _make_ai_config())
        result = engine._fallback_content("owner", _make_sources())
        assert "consumer_reactions" in result
        assert "product_hints" in result
        assert "market_ops" in result

    def test_general_fallback(self) -> None:
        engine = ActionInsightEngine(_make_pool(), _make_ai_config())
        result = engine._fallback_content("general", _make_sources())
        assert "sns_drafts" in result
        assert "engagement_methods" in result

    def test_fallback_unknown_role_returns_general_shape(self) -> None:
        engine = ActionInsightEngine(_make_pool(), _make_ai_config())
        result = engine._fallback_content("alien_role", _make_sources())
        assert "sns_drafts" in result

    def test_source_urls_capped_at_three(self) -> None:
        engine = ActionInsightEngine(_make_pool(), _make_ai_config())
        many_sources = [
            SourceItem(title="t", body="b", url=f"https://ex.com/{i}", source_type="news")
            for i in range(10)
        ]
        result = engine._fallback_content("marketer", many_sources)
        assert len(result["source_urls"]) == 3

    def test_source_urls_empty_when_no_sources(self) -> None:
        engine = ActionInsightEngine(_make_pool(), _make_ai_config())
        result = engine._fallback_content("marketer", [])
        assert result["source_urls"] == []


# ---------------------------------------------------------------------------
# _persist
# ---------------------------------------------------------------------------


class TestPersist:
    @pytest.mark.asyncio
    async def test_persist_executes_insert(self) -> None:
        pool = _make_pool()
        engine = ActionInsightEngine(pool, _make_ai_config())
        req = _make_req("marketer")
        content = {"ad_opportunities": ["test"], "source_urls": []}
        await engine._persist(req, content)
        # Verify execute was called on the connection
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.execute.assert_awaited_once()
        call_args = conn.execute.call_args
        sql: str = call_args[0][0]
        assert "INSERT INTO action_insight" in sql
        assert "$1" in sql
        assert "$2" in sql

    @pytest.mark.asyncio
    async def test_persist_does_not_raise_on_db_error(self) -> None:
        pool = _make_pool()
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.execute = AsyncMock(side_effect=Exception("DB connection refused"))
        engine = ActionInsightEngine(pool, _make_ai_config())
        req = _make_req("owner")
        # Must not raise — best-effort
        await engine._persist(req, {})


# ---------------------------------------------------------------------------
# generate() — cache hit
# ---------------------------------------------------------------------------


class TestGenerateCacheHit:
    @pytest.mark.asyncio
    async def test_returns_cached_true_on_hit(self) -> None:
        pool = _make_pool()
        engine = ActionInsightEngine(pool, _make_ai_config())
        req = _make_req("marketer")
        cached_payload = json.dumps(
            {"content": {"ad_opportunities": ["기존 캐시"], "source_urls": []}, "degraded": False}
        ).encode()

        with patch(
            "backend.processor.algorithms.action_insight.get_cached",
            new=AsyncMock(return_value=cached_payload),
        ):
            result = await engine.generate(req, _make_sources())

        assert result["cached"] is True
        assert result["content"]["ad_opportunities"] == ["기존 캐시"]

    @pytest.mark.asyncio
    async def test_cache_hit_skips_summarize(self) -> None:
        pool = _make_pool()
        engine = ActionInsightEngine(pool, _make_ai_config())
        req = _make_req("creator")
        cached_payload = json.dumps(
            {
                "content": {
                    "title_drafts": ["캐시 제목"],
                    "timing": "오전",
                    "seo_keywords": [],
                    "source_urls": [],
                },
                "degraded": False,
            }
        ).encode()

        with (
            patch(
                "backend.processor.algorithms.action_insight.get_cached",
                new=AsyncMock(return_value=cached_payload),
            ),
            patch(
                "backend.processor.algorithms.action_insight.summarize",
                new=AsyncMock(),
            ) as mock_summarize,
        ):
            await engine.generate(req, _make_sources())

        mock_summarize.assert_not_awaited()


# ---------------------------------------------------------------------------
# generate() — cache miss, AI success
# ---------------------------------------------------------------------------


class TestGenerateCacheMissAISuccess:
    @pytest.mark.asyncio
    async def test_returns_cached_false_on_miss(self) -> None:
        pool = _make_pool()
        engine = ActionInsightEngine(pool, _make_ai_config())
        req = _make_req("marketer")
        sources = _make_sources()
        ai_response = json.dumps(
            {
                "ad_opportunities": ["광고 기회 1", "광고 기회 2", "광고 기회 3"],
                "source_urls": [sources[0].url],
            }
        )

        with (
            patch(
                "backend.processor.algorithms.action_insight.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.action_insight.summarize",
                new=AsyncMock(return_value=(ai_response, False)),
            ),
            patch(
                "backend.processor.algorithms.action_insight.set_cached",
                new=AsyncMock(),
            ),
        ):
            result = await engine.generate(req, sources)

        assert result["cached"] is False
        assert result["degraded"] is False
        expected = ["광고 기회 1", "광고 기회 2", "광고 기회 3"]
        assert result["content"]["ad_opportunities"] == expected

    @pytest.mark.asyncio
    async def test_anti_hallucination_filters_invalid_urls(self) -> None:
        pool = _make_pool()
        engine = ActionInsightEngine(pool, _make_ai_config())
        req = _make_req("marketer")
        sources = _make_sources()
        hallucinated_url = "https://hallucinated.example.com/fake"
        ai_response = json.dumps(
            {
                "ad_opportunities": ["광고 기회"],
                "source_urls": [sources[0].url, hallucinated_url],
            }
        )

        with (
            patch(
                "backend.processor.algorithms.action_insight.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.action_insight.summarize",
                new=AsyncMock(return_value=(ai_response, False)),
            ),
            patch(
                "backend.processor.algorithms.action_insight.set_cached",
                new=AsyncMock(),
            ),
        ):
            result = await engine.generate(req, sources)

        assert hallucinated_url not in result["content"]["source_urls"]
        assert sources[0].url in result["content"]["source_urls"]

    @pytest.mark.asyncio
    async def test_degraded_flag_propagated(self) -> None:
        pool = _make_pool()
        engine = ActionInsightEngine(pool, _make_ai_config())
        req = _make_req("general")
        sources = _make_sources()
        ai_response = json.dumps(
            {
                "sns_drafts": ["포스트 1"],
                "engagement_methods": ["팁 1"],
                "source_urls": [],
            }
        )

        with (
            patch(
                "backend.processor.algorithms.action_insight.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.action_insight.summarize",
                new=AsyncMock(return_value=(ai_response, True)),
            ),
            patch(
                "backend.processor.algorithms.action_insight.set_cached",
                new=AsyncMock(),
            ),
        ):
            result = await engine.generate(req, sources)

        assert result["degraded"] is True


# ---------------------------------------------------------------------------
# generate() — cache miss, JSON parse failure → fallback
# ---------------------------------------------------------------------------


class TestGenerateJSONParseFallback:
    @pytest.mark.asyncio
    async def test_uses_fallback_on_invalid_json(self) -> None:
        pool = _make_pool()
        engine = ActionInsightEngine(pool, _make_ai_config())
        req = _make_req("owner")
        sources = _make_sources()

        with (
            patch(
                "backend.processor.algorithms.action_insight.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.action_insight.summarize",
                new=AsyncMock(return_value=("이것은 JSON이 아닙니다", True)),
            ),
            patch(
                "backend.processor.algorithms.action_insight.set_cached",
                new=AsyncMock(),
            ),
        ):
            result = await engine.generate(req, sources)

        assert "consumer_reactions" in result["content"]

    @pytest.mark.asyncio
    async def test_fallback_source_urls_only_valid(self) -> None:
        pool = _make_pool()
        engine = ActionInsightEngine(pool, _make_ai_config())
        req = _make_req("creator")
        sources = _make_sources()

        with (
            patch(
                "backend.processor.algorithms.action_insight.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.action_insight.summarize",
                new=AsyncMock(return_value=("{invalid json}", True)),
            ),
            patch(
                "backend.processor.algorithms.action_insight.set_cached",
                new=AsyncMock(),
            ),
        ):
            result = await engine.generate(req, sources)

        for url in result["content"]["source_urls"]:
            assert url in {s.url for s in sources}


# ---------------------------------------------------------------------------
# generate() — cache key format
# ---------------------------------------------------------------------------


class TestGenerateCacheKey:
    @pytest.mark.asyncio
    async def test_cache_key_uses_lowercase_keyword(self) -> None:
        pool = _make_pool()
        engine = ActionInsightEngine(pool, _make_ai_config())
        req = InsightRequest(keyword="AI 트렌드", role="marketer", locale="ko")
        sources = _make_sources()
        ai_response = json.dumps({"ad_opportunities": [], "source_urls": []})
        captured_keys: list[str] = []

        async def _mock_get_cached(key: str) -> bytes | None:
            captured_keys.append(key)
            return None

        with (
            patch(
                "backend.processor.algorithms.action_insight.get_cached",
                new=_mock_get_cached,
            ),
            patch(
                "backend.processor.algorithms.action_insight.summarize",
                new=AsyncMock(return_value=(ai_response, False)),
            ),
            patch(
                "backend.processor.algorithms.action_insight.set_cached",
                new=AsyncMock(),
            ),
        ):
            await engine.generate(req, sources)

        assert captured_keys[0] == "insights:marketer:ai 트렌드"
