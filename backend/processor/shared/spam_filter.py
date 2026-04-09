"""Spam filter with XGBoost (cold start: rule-based fallback).

Pipeline spec: SpamFilter (XGBoost)
Cold start uses rule-based heuristics until a trained model is available.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# --- Rule-based patterns (cold start) ---

_SPAM_URL_RATIO_THRESHOLD: float = 0.3  # >30% of text is URLs → spam
_SPAM_KEYWORD_THRESHOLD: int = 3  # ≥3 spam keywords → spam
_MIN_CONTENT_LENGTH: int = 20  # Too short → likely spam

_SPAM_KEYWORDS: frozenset[str] = frozenset(
    {
        # Korean spam patterns
        "광고",
        "홍보",
        "무료",
        "할인",
        "쿠폰",
        "이벤트",
        "당첨",
        "대출",
        "카지노",
        "도박",
        "슬롯",
        "바카라",
        "토토",
        "베팅",
        "성인",
        "만남",
        "채팅",
        "부업",
        "재택",
        "수익",
        "클릭",
        "지금바로",
        "한정",
        # English spam patterns
        "buy now",
        "free money",
        "click here",
        "limited offer",
        "casino",
        "gambling",
        "lottery",
        "prize",
        "viagra",
        "cialis",
        "weight loss",
    }
)

_URL_PATTERN: re.Pattern[str] = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_PHONE_PATTERN: re.Pattern[str] = re.compile(r"0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}")
_EXCESSIVE_CAPS_PATTERN: re.Pattern[str] = re.compile(r"[A-Z]{10,}")
_EXCESSIVE_SPECIAL_PATTERN: re.Pattern[str] = re.compile(r"[!?]{3,}")


@dataclass
class SpamResult:
    """Spam classification result."""

    is_spam: bool
    confidence: float  # 0.0-1.0
    method: str  # "xgboost" or "rule_based"
    reasons: list[str]


def _extract_features(
    text: str,
    spam_keywords: frozenset[str] | None = None,
) -> dict[str, float]:
    """Extract features for spam detection."""
    text_len = max(len(text), 1)

    # URL ratio
    urls = _URL_PATTERN.findall(text)
    url_char_count = sum(len(u) for u in urls)
    url_ratio = url_char_count / text_len

    # Spam keyword count
    kw_set = spam_keywords if spam_keywords is not None else _SPAM_KEYWORDS
    text_lower = text.lower()
    keyword_hits = sum(1 for kw in kw_set if kw in text_lower)

    # Phone number count
    phone_count = len(_PHONE_PATTERN.findall(text))

    # Excessive caps ratio
    caps_matches = _EXCESSIVE_CAPS_PATTERN.findall(text)
    caps_ratio = sum(len(m) for m in caps_matches) / text_len

    # Excessive punctuation
    special_matches = _EXCESSIVE_SPECIAL_PATTERN.findall(text)
    special_count = len(special_matches)

    # Text length
    content_length = len(text.strip())

    return {
        "url_ratio": url_ratio,
        "keyword_hits": float(keyword_hits),
        "phone_count": float(phone_count),
        "caps_ratio": caps_ratio,
        "special_count": float(special_count),
        "content_length": float(content_length),
        "url_count": float(len(urls)),
    }


def _classify_rule_based(
    text: str,
    *,
    spam_keywords: frozenset[str] | None = None,
    url_threshold: float | None = None,
    kw_threshold: int | None = None,
    min_length: int | None = None,
) -> SpamResult:
    """Rule-based spam classification (cold start fallback)."""
    _url_thr = url_threshold if url_threshold is not None else _SPAM_URL_RATIO_THRESHOLD
    _kw_thr = kw_threshold if kw_threshold is not None else _SPAM_KEYWORD_THRESHOLD
    _min_len = min_length if min_length is not None else _MIN_CONTENT_LENGTH

    features = _extract_features(text, spam_keywords)
    reasons: list[str] = []
    score = 0.0

    if features["content_length"] < _min_len:
        reasons.append("content_too_short")
        score += 0.3

    if features["url_ratio"] > _url_thr:
        reasons.append("high_url_ratio")
        score += 0.3

    if features["keyword_hits"] >= _kw_thr:
        reasons.append("spam_keywords")
        score += 0.3

    if features["phone_count"] >= 2:
        reasons.append("multiple_phone_numbers")
        score += 0.2

    if features["caps_ratio"] > 0.3:
        reasons.append("excessive_caps")
        score += 0.1

    if features["special_count"] >= 3:
        reasons.append("excessive_punctuation")
        score += 0.1

    confidence = min(1.0, score)
    is_spam = confidence >= 0.5

    return SpamResult(
        is_spam=is_spam,
        confidence=confidence,
        method="rule_based",
        reasons=reasons,
    )


# --- XGBoost model (loaded on demand) ---

_xgb_model: object | None = None
_MODEL_PATH_ENV_KEY: str = "SPAM_MODEL_PATH"


def _try_load_xgboost_model(model_path: Path | None = None) -> bool:
    """Attempt to load a trained XGBoost model."""
    global _xgb_model
    try:
        import xgboost as xgb  # type: ignore[import-untyped]

        if model_path is None or not model_path.exists():
            logger.info("spam_model_not_found", msg="using rule-based fallback")
            return False

        _xgb_model = xgb.Booster()
        _xgb_model.load_model(str(model_path))  # type: ignore[union-attr]
        logger.info("spam_model_loaded", path=str(model_path))
        return True
    except ImportError:
        logger.info("xgboost_not_installed", msg="using rule-based fallback")
        return False
    except Exception as exc:
        logger.warning("spam_model_load_failed", error=str(exc))
        _xgb_model = None
        return False


def _classify_xgboost(text: str) -> SpamResult | None:
    """Classify using XGBoost model. Returns None if model unavailable."""
    if _xgb_model is None:
        return None

    try:
        import numpy as np  # type: ignore[import-untyped]
        import xgboost as xgb  # type: ignore[import-untyped]

        features = _extract_features(text)
        feature_array = np.array(
            [
                [
                    features["url_ratio"],
                    features["keyword_hits"],
                    features["phone_count"],
                    features["caps_ratio"],
                    features["special_count"],
                    features["content_length"],
                    features["url_count"],
                ]
            ]
        )
        dmatrix = xgb.DMatrix(feature_array)
        prediction = _xgb_model.predict(dmatrix)[0]  # type: ignore[union-attr]
        confidence = float(prediction)

        return SpamResult(
            is_spam=confidence >= 0.5,
            confidence=confidence,
            method="xgboost",
            reasons=["model_prediction"],
        )
    except Exception as exc:
        logger.warning("xgboost_predict_failed", error=str(exc))
        return None


async def reload_filter_cache() -> None:
    """어드민 변경 후 필터 키워드 Redis 캐시 무효화."""
    from backend.processor.shared.config_loader import invalidate_cache

    await invalidate_cache("filter_kw")


def classify_spam(
    text: str,
    *,
    spam_keywords: frozenset[str] | None = None,
    url_threshold: float | None = None,
    kw_threshold: int | None = None,
    min_length: int | None = None,
    model_path: Path | None = None,
) -> SpamResult:
    """Classify text as spam or not.

    Uses XGBoost model if available, falls back to rule-based heuristics.
    Optional keyword/threshold overrides are used when provided (DB-loaded values).

    Args:
        text: Input text to classify.
        spam_keywords: Override spam keyword set (from DB). Falls back to hardcoded set.
        url_threshold: Override URL ratio threshold (from DB).
        kw_threshold: Override spam keyword count threshold (from DB).
        min_length: Override minimum content length (from DB).
        model_path: Optional path to trained XGBoost model file.

    Returns:
        SpamResult with classification and confidence.
    """
    if not text or not text.strip():
        return SpamResult(
            is_spam=True,
            confidence=1.0,
            method="rule_based",
            reasons=["empty_content"],
        )

    # Try XGBoost first
    if _xgb_model is None and model_path is not None:
        _try_load_xgboost_model(model_path)

    xgb_result = _classify_xgboost(text)
    if xgb_result is not None:
        return xgb_result

    # Fallback to rule-based with optional DB-loaded overrides
    return _classify_rule_based(
        text,
        spam_keywords=spam_keywords,
        url_threshold=url_threshold,
        kw_threshold=kw_threshold,
        min_length=min_length,
    )
