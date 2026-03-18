"""Sentiment analysis: KoELECTRA with lexicon fallback. (RULE 06: try/except + structlog)"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)

# --- Lexicon dictionaries ---
_POSITIVE_KEYWORDS: list[str] = [
    "좋",
    "최고",
    "훌륭",
    "성공",
    "긍정",
    "상승",
    "호황",
    "excellent",
    "good",
    "great",
    "positive",
]
_NEGATIVE_KEYWORDS: list[str] = [
    "나쁜",
    "최악",
    "실패",
    "부정",
    "하락",
    "불황",
    "bad",
    "terrible",
    "negative",
    "fail",
]

# KoELECTRA pipeline model name
_MODEL_NAME: str = "monologg/koelectra-base-finetuned-sentiment"

# Mapping from raw model labels to canonical labels
_LABEL_MAP: dict[str, str] = {
    "positive": "positive",
    "negative": "negative",
    "neutral": "neutral",
    "POSITIVE": "positive",
    "NEGATIVE": "negative",
    "NEUTRAL": "neutral",
    "LABEL_0": "negative",
    "LABEL_1": "positive",
}


@dataclass
class SentimentResult:
    """Sentiment analysis result."""

    label: str  # "positive" | "neutral" | "negative"
    score: float  # confidence [0, 1]


class SentimentAnalyzer:
    """Lazy-loading sentiment analyzer. Falls back to lexicon on ImportError."""

    def __init__(self) -> None:
        self._model: object | None = None
        self._tokenizer: object | None = None
        self._model_loaded: bool = False

    def _load_model(self) -> None:
        """Lazily load the KoELECTRA sentiment pipeline."""
        if self._model_loaded:
            return

        try:
            from transformers import pipeline  # type: ignore[import-untyped]

            self._model = pipeline(
                "text-classification",
                model=_MODEL_NAME,
            )
            self._model_loaded = True
            logger.info("sentiment_model_loaded", model=_MODEL_NAME)
        except ImportError as exc:
            logger.warning(
                "sentiment_model_unavailable",
                reason="transformers not installed",
                error=str(exc),
            )
            self._model = None
            self._model_loaded = True
        except Exception as exc:
            logger.warning(
                "sentiment_model_unavailable",
                reason="load_failed",
                error=str(exc),
            )
            self._model = None
            self._model_loaded = True

    def _lexicon_analyze(self, text: str) -> SentimentResult:
        """Fallback lexicon-based sentiment analysis."""
        lower_text = text.lower()
        words = lower_text.split()
        total_words = len(words)

        pos_count = sum(1 for keyword in _POSITIVE_KEYWORDS if keyword in lower_text)
        neg_count = sum(1 for keyword in _NEGATIVE_KEYWORDS if keyword in lower_text)

        if pos_count > neg_count:
            label = "positive"
        elif neg_count > pos_count:
            label = "negative"
        else:
            label = "neutral"

        raw_score = max(pos_count, neg_count) / max(total_words, 1)
        score = max(0.0, min(1.0, raw_score))

        return SentimentResult(label=label, score=score)

    def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment of the given text.

        Uses KoELECTRA model when available; falls back to lexicon otherwise.

        Args:
            text: Input text to analyze.

        Returns:
            SentimentResult with label and confidence score.
        """
        self._load_model()

        if self._model is not None:
            try:
                results = self._model(text[:512])  # type: ignore[operator]
                if results:
                    raw = results[0]
                    raw_label: str = raw.get("label", "neutral")
                    confidence: float = float(raw.get("score", 0.5))
                    label = _LABEL_MAP.get(raw_label, "neutral")
                    return SentimentResult(label=label, score=confidence)
            except Exception as exc:
                logger.warning(
                    "sentiment_model_inference_failed",
                    error=str(exc),
                )

        return self._lexicon_analyze(text)
