"""Tests for keyword_extractor module."""

from __future__ import annotations

from backend.processor.shared.keyword_extractor import (
    CorpusStats,
    Keyword,
    extract_keywords,
    reset_corpus_stats,
)


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
        assert "인공지능" in terms

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
