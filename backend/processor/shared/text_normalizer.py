"""Text normalization for news and SNS content. (RULE 11: single responsibility)"""

from __future__ import annotations

import html
import re
import unicodedata

import structlog

logger = structlog.get_logger(__name__)

# Patterns compiled once at module level
_URL_PATTERN: re.Pattern[str] = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_EMAIL_PATTERN: re.Pattern[str] = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", re.IGNORECASE
)
_HTML_TAG_PATTERN: re.Pattern[str] = re.compile(r"<[^>]+>")
_MULTI_SPACE_PATTERN: re.Pattern[str] = re.compile(r"\s+")
_MULTI_NEWLINE_PATTERN: re.Pattern[str] = re.compile(r"\n{3,}")
_SPECIAL_CHAR_PATTERN: re.Pattern[str] = re.compile(
    r"[^\w\s가-힣ㄱ-ㅎㅏ-ㅣぁ-ゟ゠-ヿ一-鿿.,!?;:()\"'\-–—…·]"
)
# Repeated character normalization (e.g., ㅋㅋㅋㅋ → ㅋㅋ)
_REPEATED_CHAR_PATTERN: re.Pattern[str] = re.compile(r"(.)\1{2,}")


def normalize_text(
    text: str,
    *,
    strip_urls: bool = True,
    strip_emails: bool = True,
    strip_html: bool = True,
    max_length: int = 0,
) -> str:
    """Normalize raw text for downstream NLP processing.

    Args:
        text: Raw input text.
        strip_urls: Remove URLs.
        strip_emails: Remove email addresses.
        strip_html: Remove HTML tags and decode entities.
        max_length: Truncate result to this length (0 = no limit).

    Returns:
        Cleaned, normalized text.
    """
    if not text or not text.strip():
        return ""

    result = text

    # 1. HTML entity decode + tag removal
    if strip_html:
        result = html.unescape(result)
        result = _HTML_TAG_PATTERN.sub("", result)

    # 2. Unicode normalization (NFC for Korean compatibility)
    result = unicodedata.normalize("NFC", result)

    # 3. Remove URLs
    if strip_urls:
        result = _URL_PATTERN.sub("", result)

    # 4. Remove emails
    if strip_emails:
        result = _EMAIL_PATTERN.sub("", result)

    # 5. Remove special / control characters
    result = _SPECIAL_CHAR_PATTERN.sub(" ", result)

    # 6. Normalize repeated characters (ㅋㅋㅋㅋ → ㅋㅋ)
    result = _REPEATED_CHAR_PATTERN.sub(r"\1\1", result)

    # 7. Collapse whitespace
    result = _MULTI_NEWLINE_PATTERN.sub("\n\n", result)
    result = _MULTI_SPACE_PATTERN.sub(" ", result)

    result = result.strip()

    # 8. Truncate if needed
    if max_length > 0 and len(result) > max_length:
        result = result[:max_length].rsplit(" ", 1)[0]

    return result


def normalize_title(title: str) -> str:
    """Normalize a news/article title (stricter cleaning)."""
    cleaned = normalize_text(title, strip_urls=True, strip_emails=True, strip_html=True)
    # Remove leading markers like [속보], [단독], (종합) etc.
    cleaned = re.sub(r"^[\[(【].*?[】\])][\s]*", "", cleaned)
    # Remove trailing comment/view counts: [1162], (384), 숫자만
    cleaned = re.sub(r"[\s]*[\[(]\d+[\])]\s*$", "", cleaned)
    cleaned = re.sub(r"\s+\d+\s*$", "", cleaned)
    # Remove trailing file-extension / format markers like [.txt], [.html]
    cleaned = re.sub(r"\s*[\[(]\.[a-z0-9]{1,6}[\])]\s*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()
