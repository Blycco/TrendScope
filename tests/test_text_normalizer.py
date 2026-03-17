"""Tests for text_normalizer module."""

from __future__ import annotations

from backend.processor.shared.text_normalizer import normalize_text, normalize_title


class TestNormalizeText:
    """Tests for normalize_text function."""

    def test_empty_string(self) -> None:
        assert normalize_text("") == ""

    def test_whitespace_only(self) -> None:
        assert normalize_text("   \n\t  ") == ""

    def test_html_tag_removal(self) -> None:
        result = normalize_text("<p>Hello <b>world</b></p>")
        assert "<" not in result
        assert "Hello" in result
        assert "world" in result

    def test_html_entity_decode(self) -> None:
        result = normalize_text("AT&amp;T &lt;test&gt;")
        # &amp; is decoded, then & may be stripped by special char filter
        assert "&amp;" not in result
        assert "AT" in result

    def test_url_removal(self) -> None:
        result = normalize_text("Visit https://example.com for more info")
        assert "https://" not in result
        assert "Visit" in result

    def test_url_preservation_when_disabled(self) -> None:
        result = normalize_text("Visit https://example.com", strip_urls=False)
        assert "example.com" in result

    def test_email_removal(self) -> None:
        result = normalize_text("Contact user@example.com for help")
        assert "@" not in result
        assert "Contact" in result

    def test_email_preservation_when_disabled(self) -> None:
        result = normalize_text("Contact user@example.com", strip_emails=False)
        # @ is special char, but "user" and "example.com" should remain
        assert "user" in result
        assert "example.com" in result

    def test_repeated_char_normalization(self) -> None:
        result = normalize_text("ㅋㅋㅋㅋㅋ 재밌다")
        assert "ㅋㅋㅋ" not in result
        assert "ㅋㅋ" in result

    def test_whitespace_collapse(self) -> None:
        result = normalize_text("hello    world   test")
        assert "  " not in result
        assert "hello world test" == result

    def test_unicode_normalization(self) -> None:
        # NFC normalization for Korean
        result = normalize_text("한글 테스트")
        assert "한글" in result

    def test_max_length_truncation(self) -> None:
        text = "word " * 100
        result = normalize_text(text, max_length=20)
        assert len(result) <= 20

    def test_max_length_zero_no_truncation(self) -> None:
        text = "a long text that should not be truncated"
        result = normalize_text(text, max_length=0)
        assert "truncated" in result

    def test_korean_text_preserved(self) -> None:
        result = normalize_text("대한민국 서울에서 열린 행사")
        assert "대한민국" in result
        assert "서울" in result

    def test_multiple_newlines_collapsed(self) -> None:
        result = normalize_text("para1\n\n\n\n\npara2")
        assert "\n\n\n" not in result


class TestNormalizeTitle:
    """Tests for normalize_title function."""

    def test_basic_title(self) -> None:
        result = normalize_title("Breaking News Today")
        assert result == "Breaking News Today"

    def test_korean_bracket_marker_removal(self) -> None:
        result = normalize_title("[속보] 대통령 긴급 발표")
        assert "[속보]" not in result
        assert "대통령" in result

    def test_parenthesis_marker_removal(self) -> None:
        result = normalize_title("(종합) 경제 성장률 발표")
        assert "(종합)" not in result

    def test_square_bracket_marker_removal(self) -> None:
        result = normalize_title("[단독] 새로운 정책 발표")
        assert "[단독]" not in result
        assert "새로운" in result

    def test_html_in_title(self) -> None:
        result = normalize_title("<b>Important</b> News")
        assert "<b>" not in result
        assert "Important" in result
