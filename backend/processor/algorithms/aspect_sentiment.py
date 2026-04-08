"""Aspect-Based Sentiment Analysis. (RULE 06: try/except + structlog)"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import structlog

if TYPE_CHECKING:
    pass


class _AnalyzerProtocol(Protocol):
    def analyze(self, text: str) -> object: ...


logger = structlog.get_logger(__name__)


@dataclass
class AspectSentimentResult:
    aspect: str
    positive: int
    neutral: int
    negative: int
    total: int


def extract_sentences_with_aspect(text: str, aspect: str) -> list[str]:
    """[.!?\\n] 기준으로 문장 분리 후 aspect 포함 문장 반환. 각 문장 최대 512자."""
    sentences = re.split(r"[.!?\n]+", text)
    result = []
    for s in sentences:
        s = s.strip()[:512]
        if s and aspect.lower() in s.lower():
            result.append(s)
    return result


def analyze_aspect_sentiments(
    texts: list[str],
    aspects: list[str],
    analyzer: _AnalyzerProtocol,  # SentimentAnalyzer 인스턴스
    max_sentences_per_aspect: int = 30,
) -> list[AspectSentimentResult]:
    """각 aspect별 포함 문장 수집 → 감성 분석 → 집계.

    Args:
        texts: 분석할 텍스트 목록.
        aspects: 분석할 키워드(aspect) 목록.
        analyzer: SentimentAnalyzer 인스턴스.
        max_sentences_per_aspect: aspect당 최대 분석 문장 수.

    Returns:
        total > 0인 AspectSentimentResult 목록 (total DESC 정렬).
    """
    results = []
    for aspect in aspects:
        sentences: list[str] = []
        for text in texts:
            sentences.extend(extract_sentences_with_aspect(text, aspect))

        # 샘플링
        sentences = sentences[:max_sentences_per_aspect]

        positive = neutral = negative = 0
        for sent in sentences:
            try:
                result = analyzer.analyze(sent)
                if result.label == "positive":
                    positive += 1
                elif result.label == "negative":
                    negative += 1
                else:
                    neutral += 1
            except Exception as exc:
                logger.warning(
                    "aspect_sentiment_analyze_failed",
                    aspect=aspect,
                    error=str(exc),
                )

        results.append(
            AspectSentimentResult(
                aspect=aspect,
                positive=positive,
                neutral=neutral,
                negative=negative,
                total=positive + neutral + negative,
            )
        )

    # total=0인 항목 제거 후 total DESC 정렬
    return sorted(
        [r for r in results if r.total > 0],
        key=lambda x: x.total,
        reverse=True,
    )
