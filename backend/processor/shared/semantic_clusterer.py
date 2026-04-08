"""Semantic clustering: Jaccard + MiniLM-L6 cosine similarity.

sim(A,B) = 0.50*cosine + 0.25*jaccard + 0.15*temporal + 0.10*source
Stage 1: Jaccard(keywords) — O(1) early filter
Stage 2: cosine(MiniLM-L6) — threshold dynamic per category
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

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
_MODEL_NAME: str = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"


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


def encode_text(text: str) -> list[float] | None:
    """Encode text into embedding vector using KR-SBERT."""
    model = _get_embedding_model()
    if model is None:
        return None

    try:
        embedding = model.encode(text, show_progress_bar=False)  # type: ignore[union-attr]
        return embedding.tolist()  # type: ignore[union-attr]
    except Exception as exc:
        logger.warning("text_encoding_failed", error=str(exc))
        return None


def encode_texts(texts: list[str]) -> list[list[float]]:
    """Batch-encode multiple texts into embedding vectors using KR-SBERT.

    Significantly faster than calling encode_text() individually (5-10x speedup)
    because the model processes all texts in a single forward pass.

    Returns list of embedding vectors (empty vector for failures).
    Length always matches input length.
    """
    if not texts:
        return []

    model = _get_embedding_model()
    if model is None:
        return [[] for _ in texts]

    try:
        embeddings = model.encode(texts, show_progress_bar=False, batch_size=64)  # type: ignore[union-attr]
        result: list[list[float]] = [emb.tolist() for emb in embeddings]  # type: ignore[union-attr]
        logger.debug("batch_encoding_complete", count=len(texts))
        return result
    except Exception as exc:
        logger.warning("batch_encoding_failed", error=str(exc), count=len(texts))
        return [[] for _ in texts]


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
            a.embedding = encode_text(a.text)
        if b.embedding is None:
            b.embedding = encode_text(b.text)
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


_HDBSCAN_MIN_CLUSTER_SIZE: int = 2
_HDBSCAN_MIN_ITEMS: int = 3


def _pick_representative(
    members: list[ClusterItem],
) -> tuple[ClusterItem, list[ClusterItem]]:
    """Pick the member closest to centroid as representative."""
    if len(members) == 1:
        return members[0], []

    centroid = _compute_centroid(members)
    if centroid is not None:
        best_idx = 0
        best_sim = -1.0
        for i, m in enumerate(members):
            if m.embedding is not None:
                sim = compute_cosine_similarity(m.embedding, centroid)
                if sim > best_sim:
                    best_sim = sim
                    best_idx = i
        rep = members[best_idx]
        rest = members[:best_idx] + members[best_idx + 1 :]
        return rep, rest

    return members[0], members[1:]


def _cluster_greedy(
    items: list[ClusterItem],
    threshold: float,
) -> list[Cluster]:
    """Original greedy single-linkage clustering (fallback)."""
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

    return clusters


def _cluster_hdbscan(items: list[ClusterItem]) -> list[Cluster] | None:
    """HDBSCAN density-based clustering. Returns None if unavailable."""
    if len(items) < _HDBSCAN_MIN_ITEMS:
        return None

    try:
        from sklearn.cluster import HDBSCAN as SklearnHDBSCAN  # type: ignore[import-untyped]
    except ImportError:
        logger.info("hdbscan_unavailable_fallback")
        return None

    try:
        # Build pairwise distance matrix
        n = len(items)
        dist_matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                sim = compute_similarity(items[i], items[j])
                dist = max(0.0, 1.0 - sim)
                dist_matrix[i][j] = dist
                dist_matrix[j][i] = dist

        model = SklearnHDBSCAN(
            min_cluster_size=_HDBSCAN_MIN_CLUSTER_SIZE,
            metric="precomputed",
        )
        labels = model.fit_predict(dist_matrix)

        # Group items by label
        label_groups: dict[int, list[ClusterItem]] = {}
        for item, label in zip(items, labels):  # noqa: B905
            label_groups.setdefault(int(label), []).append(item)

        clusters: list[Cluster] = []
        cluster_idx = 0

        # Real clusters (label >= 0)
        for label in sorted(k for k in label_groups if k >= 0):
            members = label_groups[label]
            rep, rest = _pick_representative(members)
            clusters.append(
                Cluster(
                    cluster_id=f"cluster_{cluster_idx}",
                    representative=rep,
                    members=rest,
                )
            )
            cluster_idx += 1

        # Noise points (label == -1) become singletons
        for noise_item in label_groups.get(-1, []):
            clusters.append(
                Cluster(
                    cluster_id=f"noise_{cluster_idx}",
                    representative=noise_item,
                )
            )
            cluster_idx += 1

        return clusters
    except Exception as exc:
        logger.warning("hdbscan_clustering_failed", error=str(exc))
        return None


def cluster_items(
    items: list[ClusterItem],
    *,
    threshold: float = _DEFAULT_CLUSTER_THRESHOLD,
) -> list[Cluster]:
    """Cluster items using HDBSCAN with greedy single-linkage fallback.

    Args:
        items: Items to cluster.
        threshold: Minimum similarity for greedy fallback.

    Returns:
        List of Cluster objects.
    """
    if not items:
        return []

    # Try HDBSCAN first
    clusters = _cluster_hdbscan(items)
    if clusters is None:
        clusters = _cluster_greedy(items, threshold)
        logger.info(
            "clustering_complete",
            method="greedy",
            input_count=len(items),
            cluster_count=len(clusters),
        )
    else:
        logger.info(
            "clustering_complete",
            method="hdbscan",
            input_count=len(items),
            cluster_count=len(clusters),
        )

    # Compute silhouette score for quality monitoring (result discarded — log only)
    all_embeddings = [item.embedding for item in items if item.embedding is not None]
    compute_silhouette_score(clusters, all_embeddings if all_embeddings else None)

    return clusters


# --- Outlier refinement ---
_OUTLIER_SIGMA: float = 1.0


def _compute_centroid(members: list[ClusterItem]) -> list[float] | None:
    """Compute the mean embedding vector of cluster members."""
    embeddings = [m.embedding for m in members if m.embedding is not None]
    if not embeddings:
        return None
    dim = len(embeddings[0])
    centroid = [0.0] * dim
    for emb in embeddings:
        for i in range(dim):
            centroid[i] += emb[i]
    n = len(embeddings)
    return [c / n for c in centroid]


def _member_similarity(
    member: ClusterItem,
    centroid: list[float] | None,
    rep_keywords: set[str],
) -> float:
    """Compute similarity of a member to the cluster centroid/representative."""
    if centroid is not None and member.embedding is not None:
        return compute_cosine_similarity(member.embedding, centroid)
    # Fallback: Jaccard against representative keywords
    if rep_keywords and member.keywords:
        return compute_jaccard(member.keywords, rep_keywords)
    return 1.0  # No data to judge → keep


def refine_clusters(
    clusters: list[Cluster],
    *,
    sigma: float = _OUTLIER_SIGMA,
) -> list[Cluster]:
    """Remove outlier members from clusters using centroid distance.

    Members with similarity below (mean - sigma * std) are separated
    into their own single-item clusters.

    Args:
        clusters: Clusters to refine.
        sigma: Standard deviation multiplier for cutoff.

    Returns:
        Refined list of clusters (outliers become singleton clusters).
    """
    refined: list[Cluster] = []
    total_removed = 0

    for cluster in clusters:
        all_members = [cluster.representative, *cluster.members]

        # Skip singleton clusters
        if len(all_members) <= 2:
            refined.append(cluster)
            continue

        # Compute centroid and representative keywords
        centroid = _compute_centroid(all_members)
        rep_keywords = cluster.representative.keywords

        # Compute per-member similarities
        sims = [_member_similarity(m, centroid, rep_keywords) for m in all_members]

        mean_sim = sum(sims) / len(sims)
        variance = sum((s - mean_sim) ** 2 for s in sims) / len(sims)
        std_sim = math.sqrt(variance)
        cutoff = mean_sim - sigma * std_sim

        # Partition: keep vs outlier
        keep: list[ClusterItem] = []
        outliers: list[ClusterItem] = []
        for member, sim in zip(all_members, sims):  # noqa: B905
            if sim >= cutoff:
                keep.append(member)
            else:
                outliers.append(member)

        if not outliers:
            refined.append(cluster)
            continue

        total_removed += len(outliers)

        # Rebuild cluster with remaining members
        if keep:
            new_rep = keep[0]
            new_cluster = Cluster(
                cluster_id=cluster.cluster_id,
                representative=new_rep,
                members=keep[1:],
            )
            refined.append(new_cluster)

        # Outliers become singleton clusters
        for outlier in outliers:
            refined.append(
                Cluster(
                    cluster_id=f"outlier_{outlier.item_id}",
                    representative=outlier,
                )
            )

    if total_removed > 0:
        logger.info(
            "cluster_refinement_complete",
            outliers_removed=total_removed,
            clusters_before=len(clusters),
            clusters_after=len(refined),
        )

    return refined


def compute_silhouette_score(
    clusters: list[Any],
    embeddings: list[list[float]] | None = None,
) -> float | None:
    """클러스터링 품질 측정. 결과는 structlog INFO 로그만 기록.

    반환값 변경 없음 — 기존 cluster_items() 시그니처 유지.
    클러스터 수 < 2 또는 총 아이템 < 4 → None.

    Args:
        clusters: Cluster 객체 목록.
        embeddings: 아이템 임베딩 벡터 목록 (없으면 None).

    Returns:
        Silhouette score (float) or None.
    """
    try:
        if len(clusters) < 2:
            return None

        # Count total items
        total_items = sum((c.size if hasattr(c, "size") else 1) for c in clusters)
        if total_items < 4:
            return None

        if not embeddings or len(embeddings) < 4:
            return None

        # Build label array: assign each embedding to a cluster index
        labels: list[int] = []
        cluster_idx = 0
        for cluster in clusters:
            cluster_size = cluster.size if hasattr(cluster, "size") else 1
            labels.extend([cluster_idx] * cluster_size)
            cluster_idx += 1

        # Trim to match embedding count if needed
        n = min(len(embeddings), len(labels))
        if n < 4:
            return None

        X = embeddings[:n]
        y = labels[:n]

        # Need at least 2 distinct labels
        if len(set(y)) < 2:
            return None

        from sklearn.metrics import silhouette_score as sk_sil  # type: ignore[import-untyped]

        score = sk_sil(X, y, metric="cosine")
        logger.info(
            "silhouette_score_computed",
            score=round(float(score), 4),
            cluster_count=len(clusters),
        )
        return float(score)

    except Exception as exc:
        logger.warning("silhouette_score_failed", error=str(exc))
        return None
