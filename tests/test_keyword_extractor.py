"""Tests for keyword_extractor module."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from backend.processor.shared.keyword_extractor import (
    CorpusStats,
    Keyword,
    _get_kiwi,
    _try_kiwi_tokenize,
    extract_keywords,
    reset_corpus_stats,
)

_kiwi_available = _get_kiwi() is not None


class TestExtractKeywords:
    """Tests for extract_keywords function."""

    def setup_method(self) -> None:
        reset_corpus_stats()

    def test_empty_text(self) -> None:
        result = extract_keywords("")
        assert result == []

    def test_whitespace_only(self) -> None:
        result = extract_keywords("   ")
        assert result == []

    def test_basic_korean_extraction(self) -> None:
        text = "인공지능 기술이 빠르게 발전하고 있다 인공지능 혁신"
        result = extract_keywords(text, use_soynlp=False)
        assert len(result) > 0
        assert all(isinstance(kw, Keyword) for kw in result)
        terms = [kw.term for kw in result]
        # kiwi splits 인공지능 → 인공 + 지능; regex keeps it whole
        assert "인공지능" in terms or ("인공" in terms and "지능" in terms)

    def test_basic_english_extraction(self) -> None:
        text = "artificial intelligence technology artificial intelligence innovation"
        result = extract_keywords(text, use_soynlp=False)
        assert len(result) > 0
        terms = [kw.term for kw in result]
        assert "artificial" in terms

    def test_stop_words_filtered(self) -> None:
        text = "the quick brown fox jumps over the lazy dog"
        result = extract_keywords(text, use_soynlp=False)
        terms = [kw.term for kw in result]
        assert "the" not in terms
        assert "over" not in terms

    def test_top_k_limit(self) -> None:
        text = "apple banana cherry date elderberry fig grape hazelnut " * 3
        result = extract_keywords(text, top_k=3, use_soynlp=False)
        assert len(result) <= 3

    def test_scores_sorted_descending(self) -> None:
        text = "python programming language python development python tools"
        result = extract_keywords(text, use_soynlp=False)
        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i].score >= result[i + 1].score

    def test_frequency_tracked(self) -> None:
        text = "python python python java java"
        result = extract_keywords(text, use_soynlp=False)
        python_kw = next((kw for kw in result if kw.term == "python"), None)
        assert python_kw is not None
        assert python_kw.frequency == 3

    def test_min_length_filtering(self) -> None:
        text = "I a to go run big cat"
        result = extract_keywords(text, use_soynlp=False)
        for kw in result:
            assert len(kw.term) >= 2

    def test_custom_corpus_stats(self) -> None:
        corpus = CorpusStats()
        text = "machine learning deep learning"
        result = extract_keywords(text, use_soynlp=False, corpus=corpus)
        assert corpus.doc_count == 1
        assert len(result) > 0

    def test_mixed_korean_english(self) -> None:
        text = "AI 인공지능 machine learning 머신러닝 technology"
        result = extract_keywords(text, use_soynlp=False)
        assert len(result) > 0
        terms = [kw.term for kw in result]
        # Should have both Korean and English
        has_korean = any(any("\uac00" <= c <= "\ud7a3" for c in t) for t in terms)
        has_english = any(t.isascii() for t in terms)
        assert has_korean
        assert has_english


class TestKiwiPosFiltering:
    """Tests for kiwipiepy POS-based keyword filtering."""

    def setup_method(self) -> None:
        reset_corpus_stats()

    @pytest.mark.skipif(not _kiwi_available, reason="kiwipiepy not installed")
    def test_verb_endings_filtered(self) -> None:
        """동사/어미 어절이 키워드에서 제거되는지 확인."""
        text = "경제가 성장하고 있지만 물가도 올랐다 기술이 발전했다"
        result = extract_keywords(text, use_soynlp=False)
        terms = [kw.term for kw in result]
        # 동사/어미 어절은 제외되어야 함
        verb_endings = {"있지만", "올랐다", "발전했다", "성장하고"}
        for verb in verb_endings:
            assert verb not in terms, f"동사/어미 '{verb}'가 키워드에 포함됨"

    def test_nouns_extracted(self) -> None:
        """명사가 정상 추출되는지 확인."""
        text = "인공지능 기술과 경제 성장이 화두다 인공지능 경제"
        result = extract_keywords(text, use_soynlp=False)
        terms = [kw.term for kw in result]
        # kiwi가 사용 가능하면 명사 추출, 아니면 regex fallback
        assert len(terms) > 0

    def test_korean_stopwords_filtered(self) -> None:
        """확장된 한국어 stopwords가 필터링되는지 확인."""
        text = "기자 연합뉴스 최근 올해 지난 현재 경제 성장"
        result = extract_keywords(text, use_soynlp=False)
        terms = [kw.term for kw in result]
        stopwords = {"기자", "연합뉴스", "최근", "올해", "지난", "현재"}
        for sw in stopwords:
            assert sw not in terms, f"stopword '{sw}'가 키워드에 포함됨"

    def test_kiwi_fallback_to_simple(self) -> None:
        """kiwi 사용 불가 시 regex fallback 동작 확인."""
        with patch(
            "backend.processor.shared.keyword_extractor._get_kiwi",
            return_value=None,
        ):
            text = "인공지능 기술이 빠르게 발전하고 있다 인공지능 혁신"
            result = extract_keywords(text, use_soynlp=False)
            assert len(result) > 0
            terms = [kw.term for kw in result]
            assert "인공지능" in terms

    @pytest.mark.skipif(not _kiwi_available, reason="kiwipiepy not installed")
    def test_kiwi_tokenize_returns_nouns(self) -> None:
        """kiwi 토크나이저가 명사만 반환하는지 직접 확인."""
        tokens = _try_kiwi_tokenize("경제가 성장하고 기술이 발전했다")
        assert tokens is not None
        verb_forms = {"성장하고", "발전했다"}
        for v in verb_forms:
            assert v not in tokens, f"동사 '{v}'가 kiwi 토큰에 포함됨"
