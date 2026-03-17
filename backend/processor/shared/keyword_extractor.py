"""Keyword extraction using soynlp + TF-IDF x BM25 scoring.

Pipeline spec: KeywordExtractor (soynlp + TF-IDF × BM25)
Falls back to simple regex-based extraction when soynlp is unavailable.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)

# --- Configuration ---
_MIN_KEYWORD_LEN: int = 2
_MAX_KEYWORD_LEN: int = 30
_DEFAULT_TOP_K: int = 10
_BM25_K1: float = 1.5
_BM25_B: float = 0.75

# Korean noun-like pattern (2+ syllable sequences)
_KOREAN_NOUN_PATTERN: re.Pattern[str] = re.compile(r"[가-힣]{2,}")
# English word pattern (2+ chars, no stop words filtered later)
_ENGLISH_WORD_PATTERN: re.Pattern[str] = re.compile(r"[a-zA-Z]{2,}")

# Minimal English stop words
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "the",
        "is",
        "at",
        "which",
        "on",
        "and",
        "or",
        "but",
        "in",
        "to",
        "for",
        "of",
        "with",
        "as",
        "by",
        "an",
        "be",
        "this",
        "that",
        "it",
        "are",
        "was",
        "were",
        "been",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "from",
        "not",
        "no",
        "if",
        "then",
        "than",
        "so",
        "up",
        "out",
        "about",
        "into",
        "over",
        "after",
        "also",
        "its",
        "his",
        "her",
    }
)

# Korean stop words (common particles / functional words)
_KOREAN_STOP_WORDS: frozenset[str] = frozenset(
    {
        "것이",
        "하는",
        "있는",
        "하고",
        "에서",
        "으로",
        "이다",
        "했다",
        "되는",
        "하며",
        "그리고",
        "또한",
        "이를",
        "통해",
        "이번",
        "대한",
        "위해",
        "관련",
        "따르면",
        "밝혔다",
        "전했다",
    }
)


@dataclass
class Keyword:
    """Extracted keyword with score."""

    term: str
    score: float
    frequency: int = 0


@dataclass
class CorpusStats:
    """Corpus-level statistics for IDF / BM25 computation."""

    doc_count: int = 0
    avg_doc_length: float = 0.0
    doc_freq: Counter[str] = field(default_factory=Counter)

    def update(self, terms: list[str], doc_length: int) -> None:
        """Update corpus stats with a new document's terms."""
        self.doc_count += 1
        self.avg_doc_length = (
            self.avg_doc_length * (self.doc_count - 1) + doc_length
        ) / self.doc_count
        unique_terms = set(terms)
        for term in unique_terms:
            self.doc_freq[term] += 1


# Module-level corpus stats (accumulates across processing batches)
_corpus_stats: CorpusStats = CorpusStats()


def get_corpus_stats() -> CorpusStats:
    """Get the current corpus statistics."""
    return _corpus_stats


def reset_corpus_stats() -> None:
    """Reset corpus statistics (e.g., on daily rotation)."""
    global _corpus_stats
    _corpus_stats = CorpusStats()
    logger.info("corpus_stats_reset")


def _tokenize_simple(text: str) -> list[str]:
    """Simple tokenization: extract Korean nouns + English words."""
    korean_tokens = _KOREAN_NOUN_PATTERN.findall(text)
    english_tokens = [w.lower() for w in _ENGLISH_WORD_PATTERN.findall(text)]
    tokens = korean_tokens + english_tokens
    return [
        t
        for t in tokens
        if _MIN_KEYWORD_LEN <= len(t) <= _MAX_KEYWORD_LEN
        and t.lower() not in _STOP_WORDS
        and t not in _KOREAN_STOP_WORDS
    ]


def _try_soynlp_tokenize(text: str) -> list[str] | None:
    """Attempt soynlp-based tokenization. Returns None if unavailable."""
    try:
        from soynlp.tokenizer import LTokenizer  # type: ignore[import-untyped]

        tokenizer = LTokenizer()
        tokens = tokenizer.tokenize(text)
        return [
            t
            for t in tokens
            if _MIN_KEYWORD_LEN <= len(t) <= _MAX_KEYWORD_LEN
            and t.lower() not in _STOP_WORDS
            and t not in _KOREAN_STOP_WORDS
        ]
    except ImportError:
        return None
    except Exception as exc:
        logger.warning("soynlp_tokenize_failed", error=str(exc))
        return None


def _compute_tf(term: str, term_counts: Counter[str], doc_length: int) -> float:
    """Raw term frequency normalized by document length."""
    if doc_length == 0:
        return 0.0
    return term_counts[term] / doc_length


def _compute_idf(term: str, corpus: CorpusStats) -> float:
    """Inverse document frequency with smoothing."""
    if corpus.doc_count == 0:
        return 1.0
    df = corpus.doc_freq.get(term, 0)
    return math.log((corpus.doc_count - df + 0.5) / (df + 0.5) + 1)


def _compute_bm25(
    term: str,
    term_counts: Counter[str],
    doc_length: int,
    corpus: CorpusStats,
) -> float:
    """BM25 score for a term in a document."""
    tf = term_counts[term]
    idf = _compute_idf(term, corpus)
    avg_dl = corpus.avg_doc_length if corpus.avg_doc_length > 0 else doc_length
    numerator = tf * (_BM25_K1 + 1)
    denominator = tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * doc_length / avg_dl)
    return idf * numerator / denominator if denominator > 0 else 0.0


def extract_keywords(
    text: str,
    *,
    top_k: int = _DEFAULT_TOP_K,
    use_soynlp: bool = True,
    corpus: CorpusStats | None = None,
) -> list[Keyword]:
    """Extract top-k keywords from text using TF-IDF x BM25 scoring.

    Args:
        text: Input text (should be pre-normalized).
        top_k: Number of keywords to return.
        use_soynlp: Attempt soynlp tokenization first.
        corpus: Corpus stats for IDF computation. Uses module-level stats if None.

    Returns:
        List of Keyword objects sorted by score descending.
    """
    if not text or not text.strip():
        return []

    # Tokenize
    tokens: list[str] | None = None
    if use_soynlp:
        tokens = _try_soynlp_tokenize(text)
    if tokens is None:
        tokens = _tokenize_simple(text)

    if not tokens:
        return []

    stats = corpus if corpus is not None else _corpus_stats
    term_counts = Counter(tokens)
    doc_length = len(tokens)

    # Update corpus stats
    stats.update(tokens, doc_length)

    # Score each unique term: TF-IDF × BM25
    scored: list[Keyword] = []
    for term, freq in term_counts.items():
        tf_idf = _compute_tf(term, term_counts, doc_length) * _compute_idf(term, stats)
        bm25 = _compute_bm25(term, term_counts, doc_length, stats)
        combined = tf_idf * bm25
        scored.append(Keyword(term=term, score=combined, frequency=freq))

    scored.sort(key=lambda kw: kw.score, reverse=True)
    return scored[:top_k]
