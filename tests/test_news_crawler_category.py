"""Tests for news_crawler._infer_category."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from backend.crawler.sources.news_crawler import _infer_category


def _make_pool() -> MagicMock:
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return pool


_CATEGORY_MAP = {
    "sports": [("축구", 1.5), ("야구", 1.5), ("선수", 1.0), ("경기", 1.0)],
    "economy": [("주가", 1.5), ("코스피", 1.5), ("금리", 1.2), ("투자", 1.0)],
    "tech": [("AI", 1.5), ("반도체", 1.5), ("스타트업", 1.2)],
}


async def test_infer_sports_category() -> None:
    """스포츠 키워드 매칭 → 'sports' 반환."""
    with patch(
        "backend.processor.shared.config_loader.get_category_keywords",
        new_callable=AsyncMock,
        return_value=_CATEGORY_MAP,
    ):
        pool = _make_pool()
        result = await _infer_category("축구 월드컵 경기", "선수 리그 우승", "general", pool)
    assert result == "sports"


async def test_infer_economy_category() -> None:
    """경제 키워드 매칭 → 'economy' 반환."""
    with patch(
        "backend.processor.shared.config_loader.get_category_keywords",
        new_callable=AsyncMock,
        return_value=_CATEGORY_MAP,
    ):
        result = await _infer_category("주가 코스피 금리", "투자 증시", "general", _make_pool())
    assert result == "economy"


async def test_infer_falls_back_below_threshold() -> None:
    """매칭 합계 < 3.0 → feed_category 반환."""
    with patch(
        "backend.processor.shared.config_loader.get_category_keywords",
        new_callable=AsyncMock,
        return_value=_CATEGORY_MAP,
    ):
        result = await _infer_category("날씨 맑음", "오늘 날씨", "general", _make_pool())
    assert result == "general"


async def test_infer_falls_back_on_empty_map() -> None:
    """category_keyword가 없으면 feed_category 반환."""
    with patch(
        "backend.processor.shared.config_loader.get_category_keywords",
        new_callable=AsyncMock,
        return_value={},
    ):
        result = await _infer_category("축구 선수", "경기 우승", "sports", _make_pool())
    assert result == "sports"


async def test_infer_falls_back_on_exception() -> None:
    """예외 발생 시 feed_category 반환."""
    with patch(
        "backend.processor.shared.config_loader.get_category_keywords",
        new_callable=AsyncMock,
        side_effect=Exception("DB error"),
    ):
        result = await _infer_category("축구", "경기", "general", _make_pool())
    assert result == "general"
