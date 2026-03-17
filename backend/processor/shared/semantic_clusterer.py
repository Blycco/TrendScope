"""Semantic clustering: Jaccard + MiniLM-L6 cosine similarity.

sim(A,B) = 0.50*cosine + 0.25*jaccard + 0.15*temporal + 0.10*source
Stage 1: Jaccard(keywords) — O(1) early filter
Stage 2: cosine(MiniLM-L6) — threshold dynamic per category
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger(__name__)

# --- Similarity weights (from algorithms.md) ---
_COSINE_WEIGHT: float = 0.50
_JACCARD_WEIGHT: float = 0.25
_TEMPORAL_WEIGHT: float = 0.15
_SOURCE_WEIGHT: float = 0.10

# Thresholds
_JACCARD_EARLY_FILTER: float = 0.10  # Skip cosine if Jaccard < this
_DEFAULT_CLUSTER_THRESHOLD: float = 0.55
_TEMPORAL_DECAY_HOURS: float = 24.0  # Time window for temporal similarity

# Sentence transformer model (loaded lazily)
_embedding_model: object | None = None
_MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L6-v2"


@dataclass
class ClusterItem:
    """An item to be clustered."""

    item_id: str
    text: str
    keywords: set[str] = field(default_factory=set)
    published_at: datetime | None = None
    source_type: str = ""
    embedding: list[float] | None = None


@dataclass
class Cluster:
    """A cluster of similar items."""

    cluster_id: str
    representative: ClusterItem
    members: list[ClusterItem] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.members) + 1  # representative + members


def compute_jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two keyword sets."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


def compute_temporal_similarity(
    a: datetime | None,
    b: datetime | None,
    decay_hours: float = _TEMPORAL_DECAY_HOURS,
) -> float:
    """Temporal proximity score (exponential decay by hour difference)."""
    if a is None or b is None:
        return 0.5  # Neutral score when timestamps unknown

    if a.tzinfo is None:
        a = a.replace(tzinfo=timezone.utc)  # noqa: UP017
    if b.tzinfo is None:
        b = b.replace(tzinfo=timezone.utc)  # noqa: UP017

    hours_diff = abs((a - b).total_seconds()) / 3600.0
    return math.exp(-hours_diff / decay_hours)


def compute_source_similarity(a: str, b: str) -> float:
    """Source type similarity (same type = 1.0, different = 0.0)."""
    if not a or not b:
        return 0.5
    return 1.0 if a == b else 0.0


def _get_embedding_model() -> object | None:
    """Lazily load the sentence transformer model."""
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

        _embedding_model = SentenceTransformer(_MODEL_NAME)
        logger.info("embedding_model_loaded", model=_MODEL_NAME)
        return _embedding_model
    except ImportError:
        logger.info("sentence_transformers_not_installed", msg="cosine similarity unavailable")
        return None
    except Exception as exc:
        logger.warning("embedding_model_load_failed", error=str(exc))
        return None


def compute_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))  # noqa: B905
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _encode_text(text: str) -> list[float] | None:
    """Encode text into embedding vector using MiniLM-L6."""
    model = _get_embedding_model()
    if model is None:
        return None

    try:
        embedding = model.encode(text, show_progress_bar=False)  # type: ignore[union-attr]
        return embedding.tolist()  # type: ignore[union-attr]
    except Exception as exc:
        logger.warning("text_encoding_failed", error=str(exc))
        return None


def compute_similarity(a: ClusterItem, b: ClusterItem) -> float:
    """Compute composite similarity between two items.

    sim(A,B) = 0.50*cosine + 0.25*jaccard + 0.15*temporal + 0.10*source

    Uses Jaccard as early filter (Stage 1) before computing cosine (Stage 2).
    """
    # Stage 1: Jaccard early filter
    jaccard = compute_jaccard(a.keywords, b.keywords)
    if jaccard < _JACCARD_EARLY_FILTER and (a.embedding is None or b.embedding is None):
        # Very low keyword overlap and no embeddings → skip
        return jaccard * _JACCARD_WEIGHT

    # Stage 2: Cosine similarity
    cosine = 0.0
    if a.embedding is not None and b.embedding is not None:
        cosine = compute_cosine_similarity(a.embedding, b.embedding)
    else:
        # Try to compute embeddings
        if a.embedding is None:
            a.embedding = _encode_text(a.text)
        if b.embedding is None:
            b.embedding = _encode_text(b.text)
        if a.embedding is not None and b.embedding is not None:
            cosine = compute_cosine_similarity(a.embedding, b.embedding)

    temporal = compute_temporal_similarity(a.published_at, b.published_at)
    source = compute_source_similarity(a.source_type, b.source_type)

    return (
        _COSINE_WEIGHT * cosine
        + _JACCARD_WEIGHT * jaccard
        + _TEMPORAL_WEIGHT * temporal
        + _SOURCE_WEIGHT * source
    )


def cluster_items(
    items: list[ClusterItem],
    *,
    threshold: float = _DEFAULT_CLUSTER_THRESHOLD,
) -> list[Cluster]:
    """Cluster items using greedy single-linkage with composite similarity.

    Args:
        items: Items to cluster.
        threshold: Minimum similarity to join a cluster.

    Returns:
        List of Cluster objects.
    """
    if not items:
        return []

    clusters: list[Cluster] = []

    for item in items:
        best_cluster: Cluster | None = None
        best_sim: float = 0.0

        for cluster in clusters:
            sim = compute_similarity(item, cluster.representative)
            if sim > best_sim:
                best_sim = sim
                best_cluster = cluster

        if best_cluster is not None and best_sim >= threshold:
            best_cluster.members.append(item)
            logger.debug(
                "item_clustered",
                item_id=item.item_id,
                cluster_id=best_cluster.cluster_id,
                similarity=round(best_sim, 4),
            )
        else:
            new_cluster = Cluster(
                cluster_id=f"cluster_{len(clusters)}",
                representative=item,
            )
            clusters.append(new_cluster)

    logger.info(
        "clustering_complete",
        input_count=len(items),
        cluster_count=len(clusters),
    )

    return clusters
