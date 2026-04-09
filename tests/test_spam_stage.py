"""Tests for backend/processor/stages/spam_filter.py (async stage with DB config)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.processor.stages.spam_filter import stage_spam_filter


def _pool() -> MagicMock:
    return MagicMock()


def _article(title: str = "뉴스 기사", body: str = "내용이 있는 뉴스 기사입니다.") -> dict:
    return {"url": "https://example.com", "title": title, "body": body}


def _mock_settings(url: float = 0.3, kw: int = 3, min_len: int = 20, hits: int = 2):
    return AsyncMock(side_effect=[url, kw, min_len, hits])


def _mock_filter_kw(kw: frozenset | None = None):
    return AsyncMock(return_value=kw or frozenset())


class TestStageSpamFilterAsync:
    @pytest.mark.asyncio
    async def test_clean_article_passes(self) -> None:
        articles = [_article()]
        with (
            patch("backend.processor.stages.spam_filter.get_setting", _mock_settings()),
            patch("backend.processor.stages.spam_filter.get_filter_keywords", _mock_filter_kw()),
        ):
            result = await stage_spam_filter(articles, _pool())
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_spam_article_filtered(self) -> None:
        articles = [
            _article(
                title="무료 대출 카지노 도박 바카라",
                body="무료 카지노 도박 대출 할인 쿠폰 이벤트 당첨 " * 5,
            )
        ]
        with (
            patch("backend.processor.stages.spam_filter.get_setting", _mock_settings()),
            patch(
                "backend.processor.stages.spam_filter.get_filter_keywords",
                AsyncMock(
                    return_value=frozenset({"무료", "카지노", "도박", "대출", "할인", "쿠폰"})
                ),
            ),
        ):
            result = await stage_spam_filter(articles, _pool())
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_obituary_article_filtered(self) -> None:
        articles = [_article(title="故 홍길동씨 별세 부고 장례식", body="향년 90세, 발인은 내일")]
        obituary_kw = frozenset({"부고", "별세", "발인", "향년", "장례식"})

        call_count = 0

        async def side_effect_filter(pool, category=None):
            nonlocal call_count
            call_count += 1
            if category == "obituary":
                return obituary_kw
            return frozenset()

        with (
            patch("backend.processor.stages.spam_filter.get_setting", _mock_settings()),
            patch("backend.processor.stages.spam_filter.get_filter_keywords", side_effect_filter),
        ):
            result = await stage_spam_filter(articles, _pool())
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_obituary_single_hit_passes(self) -> None:
        """1개 부고 키워드만 있으면 non_trend_min_hits=2 기준으로 통과."""
        articles = [_article(title="별세 소식", body="정상적인 뉴스 내용입니다.")]
        obituary_kw = frozenset({"부고", "별세", "발인"})

        async def side_effect_filter(pool, category=None):
            if category == "obituary":
                return obituary_kw
            return frozenset()

        with (
            patch("backend.processor.stages.spam_filter.get_setting", _mock_settings(hits=2)),
            patch("backend.processor.stages.spam_filter.get_filter_keywords", side_effect_filter),
        ):
            result = await stage_spam_filter(articles, _pool())
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_config_load_failure_uses_defaults(self) -> None:
        """설정 로드 실패 시 하드코딩 기본값으로 폴백."""
        articles = [_article()]
        with patch(
            "backend.processor.stages.spam_filter.get_setting",
            AsyncMock(side_effect=RuntimeError("Redis down")),
        ):
            result = await stage_spam_filter(articles, _pool())
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_empty_articles_returns_empty(self) -> None:
        with (
            patch("backend.processor.stages.spam_filter.get_setting", _mock_settings()),
            patch("backend.processor.stages.spam_filter.get_filter_keywords", _mock_filter_kw()),
        ):
            result = await stage_spam_filter([], _pool())
        assert result == []

    @pytest.mark.asyncio
    async def test_article_error_passes_through(self) -> None:
        """개별 기사 처리 오류 시 기사를 통과시킨다."""
        articles = [{"url": "x", "title": None, "body": None}]
        with (
            patch("backend.processor.stages.spam_filter.get_setting", _mock_settings()),
            patch("backend.processor.stages.spam_filter.get_filter_keywords", _mock_filter_kw()),
        ):
            result = await stage_spam_filter(articles, _pool())
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_db_spam_keywords_used(self) -> None:
        """DB에서 로드한 스팸 키워드가 실제 분류에 사용된다."""
        custom_kw = frozenset({"커스텀스팸", "특수광고", "비밀쿠폰"})
        articles = [
            _article(
                title="커스텀스팸 특수광고 비밀쿠폰",
                body="커스텀스팸 특수광고 비밀쿠폰 " * 5,
            )
        ]
        with (
            patch("backend.processor.stages.spam_filter.get_setting", _mock_settings()),
            patch(
                "backend.processor.stages.spam_filter.get_filter_keywords",
                AsyncMock(return_value=custom_kw),
            ),
        ):
            result = await stage_spam_filter(articles, _pool())
        assert len(result) == 0
