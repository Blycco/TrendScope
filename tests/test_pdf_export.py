"""Unit tests for PDF export utility."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.api.utils.pdf_export import generate_trends_pdf


def _row(
    title: str = "테스트 트렌드",
    category: str = "tech",
    score: float = 8.5,
    keywords: list[str] | None = None,
) -> dict:
    return {
        "title": title,
        "category": category,
        "score": score,
        "early_trend_score": 0.5,
        "keywords": keywords or ["AI", "트렌드"],
        "created_at": datetime(2026, 3, 19, tzinfo=timezone.utc),
    }


class TestGenerateTrendsPdf:
    def test_returns_valid_pdf_bytes(self) -> None:
        result = generate_trends_pdf([_row()])
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_empty_rows_returns_valid_pdf(self) -> None:
        result = generate_trends_pdf([])
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_multiple_rows(self) -> None:
        rows = [_row(title=f"트렌드 {i}", score=float(i)) for i in range(10)]
        result = generate_trends_pdf(rows)
        assert result[:5] == b"%PDF-"
        assert len(result) > 500

    def test_none_keywords_handled(self) -> None:
        result = generate_trends_pdf([_row(keywords=None)])
        assert result[:5] == b"%PDF-"

    def test_none_created_at_handled(self) -> None:
        row = _row()
        row["created_at"] = None
        result = generate_trends_pdf([row])
        assert result[:5] == b"%PDF-"

    def test_long_title_does_not_crash(self) -> None:
        result = generate_trends_pdf([_row(title="가" * 200)])
        assert result[:5] == b"%PDF-"
