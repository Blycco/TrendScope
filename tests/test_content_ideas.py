"""Tests for ContentIdeasEngine (content_ideas.py).

Coverage targets:
- generate(): cache hit, cache miss + AI success, cache miss + JSON parse failure
- ROUGE gate trigger → fallback
- _rouge1_recall() edge cases
- _fallback_ideas() all roles
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.processor.algorithms.content_ideas import (
    ContentIdeasEngine,
    _fallback_ideas,
    _rouge1_recall,
)
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


def _make_sources() -> list[dict]:
    return [
        {
            "title": "AI 트렌드 급상승",
            "body": "인공지능 관련 검색량이 급격히 증가하고 있습니다.",
        },
        {
            "title": "SNS 반응",
            "body": "소셜미디어에서 AI 관련 게시물이 폭발적으로 증가.",
        },
    ]


def _make_valid_ai_response() -> str:
    # Use ensure_ascii=False so Korean chars appear as-is (matching source text words)
    return json.dumps(
        [
            {
                "title": "AI 마케팅 전략",
                "hook": "AI 트렌드를 활용하세요.",
                "platform": "youtube",
                "difficulty": "medium",
            },
            {
                "title": "AI 콘텐츠 기획",
                "hook": "인공지능으로 콘텐츠를 만들어보세요.",
                "platform": "instagram",
                "difficulty": "easy",
            },
            {
                "title": "AI 비즈니스 활용",
                "hook": "AI로 비즈니스를 성장시키세요.",
                "platform": "blog",
                "difficulty": "hard",
            },
        ],
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# _rouge1_recall
# ---------------------------------------------------------------------------


class TestRouge1Recall:
    def test_identical_strings_returns_one(self) -> None:
        assert _rouge1_recall("hello world", "hello world") == 1.0

    def test_empty_reference_returns_zero(self) -> None:
        assert _rouge1_recall("hello", "") == 0.0

    def test_no_overlap_returns_zero(self) -> None:
        assert _rouge1_recall("foo bar", "baz qux") == 0.0

    def test_partial_overlap(self) -> None:
        # hyp = {hello, world}, ref = {hello, world, foo} → 2/3
        result = _rouge1_recall("hello world", "hello world foo")
        assert abs(result - 2 / 3) < 1e-9

    def test_case_insensitive(self) -> None:
        result = _rouge1_recall("Hello World", "hello world")
        assert result == 1.0


# ---------------------------------------------------------------------------
# _fallback_ideas
# ---------------------------------------------------------------------------


class TestFallbackIdeas:
    def test_returns_three_ideas(self) -> None:
        ideas = _fallback_ideas("AI", "general")
        assert len(ideas) == 3

    def test_marketer_ideas_contain_keyword(self) -> None:
        ideas = _fallback_ideas("AI", "marketer")
        assert all("AI" in idea.title for idea in ideas)

    def test_owner_ideas_contain_keyword(self) -> None:
        ideas = _fallback_ideas("AI", "owner")
        assert all("AI" in idea.title for idea in ideas)

    def test_general_ideas_contain_keyword(self) -> None:
        ideas = _fallback_ideas("AI", "general")
        assert all("AI" in idea.title for idea in ideas)

    def test_creator_falls_back_to_general(self) -> None:
        ideas = _fallback_ideas("AI", "creator")
        assert len(ideas) == 3

    def test_platforms_are_valid(self) -> None:
        valid = {"youtube", "instagram", "blog", "newsletter"}
        ideas = _fallback_ideas("트렌드", "general")
        for idea in ideas:
            assert idea.platform in valid

    def test_difficulties_are_valid(self) -> None:
        valid = {"easy", "medium", "hard"}
        ideas = _fallback_ideas("트렌드", "marketer")
        for idea in ideas:
            assert idea.difficulty in valid


# ---------------------------------------------------------------------------
# generate() — cache hit
# ---------------------------------------------------------------------------


class TestGenerateCacheHit:
    @pytest.mark.asyncio
    async def test_returns_cached_true_on_hit(self) -> None:
        engine = ContentIdeasEngine(_make_pool(), _make_ai_config())
        idea = {"title": "캐시 아이디어", "hook": "훅", "platform": "blog", "difficulty": "easy"}
        cached_payload = json.dumps({"ideas": [idea], "degraded": False}).encode()

        with patch(
            "backend.processor.algorithms.content_ideas.get_cached",
            new=AsyncMock(return_value=cached_payload),
        ):
            result = await engine.generate("AI", "general", _make_sources())

        assert result["cached"] is True
        assert result["ideas"][0]["title"] == "캐시 아이디어"

    @pytest.mark.asyncio
    async def test_cache_hit_skips_summarize(self) -> None:
        engine = ContentIdeasEngine(_make_pool(), _make_ai_config())
        cached_payload = json.dumps(
            {
                "ideas": [],
                "degraded": False,
            }
        ).encode()

        with (
            patch(
                "backend.processor.algorithms.content_ideas.get_cached",
                new=AsyncMock(return_value=cached_payload),
            ),
            patch(
                "backend.processor.algorithms.content_ideas.summarize",
                new=AsyncMock(),
            ) as mock_summarize,
        ):
            await engine.generate("AI", "general", _make_sources())

        mock_summarize.assert_not_awaited()


# ---------------------------------------------------------------------------
# generate() — cache miss, AI success
# ---------------------------------------------------------------------------


class TestGenerateCacheMissAISuccess:
    @pytest.mark.asyncio
    async def test_returns_cached_false_on_miss(self) -> None:
        engine = ContentIdeasEngine(_make_pool(), _make_ai_config())
        # Sources that share words with the AI response to pass ROUGE gate
        sources = [
            {
                "title": "AI marketing strategy",
                "body": "AI 마케팅 전략 콘텐츠 인공지능 비즈니스 기획",
            }
        ]

        with (
            patch(
                "backend.processor.algorithms.content_ideas.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.content_ideas.summarize",
                new=AsyncMock(return_value=(_make_valid_ai_response(), False)),
            ),
            patch(
                "backend.processor.algorithms.content_ideas.set_cached",
                new=AsyncMock(),
            ),
        ):
            result = await engine.generate("AI", "marketer", sources)

        assert result["cached"] is False
        assert result["degraded"] is False
        assert len(result["ideas"]) == 3

    @pytest.mark.asyncio
    async def test_ideas_have_required_fields(self) -> None:
        engine = ContentIdeasEngine(_make_pool(), _make_ai_config())

        with (
            patch(
                "backend.processor.algorithms.content_ideas.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.content_ideas.summarize",
                new=AsyncMock(return_value=(_make_valid_ai_response(), False)),
            ),
            patch(
                "backend.processor.algorithms.content_ideas.set_cached",
                new=AsyncMock(),
            ),
        ):
            result = await engine.generate("AI", "creator", _make_sources())

        for idea in result["ideas"]:
            assert "title" in idea
            assert "hook" in idea
            assert "platform" in idea
            assert "difficulty" in idea


# ---------------------------------------------------------------------------
# generate() — ROUGE gate trigger
# ---------------------------------------------------------------------------


class TestRougeGate:
    @pytest.mark.asyncio
    async def test_rouge_gate_triggers_fallback(self) -> None:
        engine = ContentIdeasEngine(_make_pool(), _make_ai_config())
        sources = _make_sources()

        # AI response with no overlap with source text
        unrelated_response = json.dumps(
            [
                {
                    "title": "xyz abc",
                    "hook": "xyz abc def",
                    "platform": "blog",
                    "difficulty": "easy",
                },
                {
                    "title": "foo bar",
                    "hook": "foo bar baz",
                    "platform": "youtube",
                    "difficulty": "medium",
                },
                {
                    "title": "qux quux",
                    "hook": "qux quux corge",
                    "platform": "instagram",
                    "difficulty": "hard",
                },
            ]
        )

        with (
            patch(
                "backend.processor.algorithms.content_ideas.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.content_ideas.summarize",
                new=AsyncMock(return_value=(unrelated_response, False)),
            ),
            patch(
                "backend.processor.algorithms.content_ideas.set_cached",
                new=AsyncMock(),
            ),
        ):
            result = await engine.generate("AI", "general", sources)

        # With zero ROUGE overlap, gate triggers and fallback is used
        assert result["degraded"] is True

    @pytest.mark.asyncio
    async def test_degraded_ai_skips_rouge_gate(self) -> None:
        """Already-degraded results (TextRank fallback) should skip ROUGE gate."""
        engine = ContentIdeasEngine(_make_pool(), _make_ai_config())
        sources = _make_sources()

        with (
            patch(
                "backend.processor.algorithms.content_ideas.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.content_ideas.summarize",
                new=AsyncMock(return_value=("not json", True)),
            ),
            patch(
                "backend.processor.algorithms.content_ideas.set_cached",
                new=AsyncMock(),
            ),
        ):
            result = await engine.generate("AI", "general", sources)

        # Falls back due to JSON parse failure, not ROUGE gate
        assert result["degraded"] is True
        assert len(result["ideas"]) == 3


# ---------------------------------------------------------------------------
# generate() — JSON parse failure fallback
# ---------------------------------------------------------------------------


class TestGenerateJSONParseFallback:
    @pytest.mark.asyncio
    async def test_uses_fallback_on_invalid_json(self) -> None:
        engine = ContentIdeasEngine(_make_pool(), _make_ai_config())
        sources = _make_sources()

        with (
            patch(
                "backend.processor.algorithms.content_ideas.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.content_ideas.summarize",
                new=AsyncMock(return_value=("이것은 JSON이 아닙니다", True)),
            ),
            patch(
                "backend.processor.algorithms.content_ideas.set_cached",
                new=AsyncMock(),
            ),
        ):
            result = await engine.generate("트렌드", "marketer", sources)

        assert len(result["ideas"]) == 3
        assert result["degraded"] is True

    @pytest.mark.asyncio
    async def test_uses_fallback_when_not_array(self) -> None:
        engine = ContentIdeasEngine(_make_pool(), _make_ai_config())
        sources = _make_sources()
        # Return a dict instead of array — valid JSON but wrong shape
        dict_response = json.dumps({"title": "인공지능 관련 검색량 소셜미디어 내용"})

        with (
            patch(
                "backend.processor.algorithms.content_ideas.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "backend.processor.algorithms.content_ideas.summarize",
                new=AsyncMock(return_value=(dict_response, False)),
            ),
            patch(
                "backend.processor.algorithms.content_ideas.set_cached",
                new=AsyncMock(),
            ),
        ):
            result = await engine.generate("AI", "general", sources)

        assert len(result["ideas"]) == 3


# ---------------------------------------------------------------------------
# generate() — cache key format
# ---------------------------------------------------------------------------


class TestGenerateCacheKey:
    @pytest.mark.asyncio
    async def test_cache_key_uses_lowercase_keyword(self) -> None:
        engine = ContentIdeasEngine(_make_pool(), _make_ai_config())
        captured_keys: list[str] = []

        async def _mock_get_cached(key: str) -> bytes | None:
            captured_keys.append(key)
            return None

        with (
            patch(
                "backend.processor.algorithms.content_ideas.get_cached",
                new=_mock_get_cached,
            ),
            patch(
                "backend.processor.algorithms.content_ideas.summarize",
                new=AsyncMock(return_value=(_make_valid_ai_response(), False)),
            ),
            patch(
                "backend.processor.algorithms.content_ideas.set_cached",
                new=AsyncMock(),
            ),
        ):
            await engine.generate("AI 트렌드", "marketer", _make_sources())

        assert captured_keys[0] == "content_ideas:marketer:ai 트렌드"
