"""Tests for spam_filter module."""

from __future__ import annotations

from backend.processor.shared.spam_filter import SpamResult, classify_spam


class TestClassifySpam:
    """Tests for classify_spam function."""

    def test_empty_text_is_spam(self) -> None:
        result = classify_spam("")
        assert result.is_spam is True
        assert result.confidence == 1.0
        assert "empty_content" in result.reasons

    def test_whitespace_is_spam(self) -> None:
        result = classify_spam("   ")
        assert result.is_spam is True

    def test_normal_news_not_spam(self) -> None:
        text = (
            "서울시는 오늘 새로운 교통 정책을 발표했다. "
            "이 정책은 대중교통 이용을 촉진하기 위한 것으로, "
            "시민들의 편의를 높이는 데 초점을 맞추고 있다."
        )
        result = classify_spam(text)
        assert result.is_spam is False
        assert result.method == "rule_based"

    def test_spam_keywords_detected(self) -> None:
        text = "무료 쿠폰 당첨 할인 이벤트 카지노 도박 대출 지금바로 클릭"
        result = classify_spam(text)
        assert "spam_keywords" in result.reasons
        assert result.confidence > 0.0

    def test_high_url_ratio_detected(self) -> None:
        text = "https://spam1.com https://spam2.com https://spam3.com click"
        result = classify_spam(text)
        assert "high_url_ratio" in result.reasons
        assert result.confidence > 0.0

    def test_short_content_flagged(self) -> None:
        text = "buy now"
        result = classify_spam(text)
        assert "content_too_short" in result.reasons

    def test_multiple_phone_numbers(self) -> None:
        text = "연락처 010-1234-5678 또는 02-123-4567 상담 문의 바랍니다 여기로 전화주세요"
        result = classify_spam(text)
        assert "multiple_phone_numbers" in result.reasons

    def test_result_dataclass(self) -> None:
        result = classify_spam("normal text content that is long enough to pass")
        assert isinstance(result, SpamResult)
        assert isinstance(result.is_spam, bool)
        assert 0.0 <= result.confidence <= 1.0
        assert result.method in ("rule_based", "xgboost")
        assert isinstance(result.reasons, list)

    def test_confidence_capped_at_one(self) -> None:
        # Combine all spam signals
        text = "무료 카지노 도박 대출 https://a.com https://b.com 010-1234-5678 011-2345-6789 !!"
        result = classify_spam(text)
        assert result.confidence <= 1.0

    def test_excessive_caps_flagged(self) -> None:
        # Needs 10+ consecutive uppercase chars (pattern: [A-Z]{10,}) and ratio > 0.3
        text = "ABCDEFGHIJK normal short"
        result = classify_spam(text)
        assert "excessive_caps" in result.reasons

    def test_excessive_punctuation_flagged(self) -> None:
        text = "great deal!!! buy now!!! limited!!! offer!!!"
        result = classify_spam(text)
        assert "excessive_punctuation" in result.reasons
