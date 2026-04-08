"""Tests for growth_classifier and compute_silhouette_score. (7건 이상)"""

from __future__ import annotations

from backend.processor.algorithms.growth_classifier import (
    GrowthType,
    VelocityWindow,
    classify_growth_type,
)
from backend.processor.shared.semantic_clusterer import (
    Cluster,
    ClusterItem,
    compute_silhouette_score,
)

# ---------------------------------------------------------------------------
# classify_growth_type tests
# ---------------------------------------------------------------------------


def test_spike_detection() -> None:
    """recent >= 3 * mid AND mid <= 2 → SPIKE."""
    windows = [
        VelocityWindow(0, 12, 30),
        VelocityWindow(12, 24, 2),
    ]
    result = classify_growth_type(windows)
    assert result == GrowthType.SPIKE


def test_growth_detection_three_windows() -> None:
    """recent >= mid * 1.2 AND mid >= old * 1.1 → GROWTH."""
    windows = [
        VelocityWindow(0, 12, 12),
        VelocityWindow(12, 24, 10),
        VelocityWindow(24, 36, 8),
    ]
    result = classify_growth_type(windows)
    assert result == GrowthType.GROWTH


def test_unknown_flat_trend() -> None:
    """Flat article counts → UNKNOWN."""
    windows = [
        VelocityWindow(0, 12, 5),
        VelocityWindow(12, 24, 5),
        VelocityWindow(24, 36, 5),
    ]
    result = classify_growth_type(windows)
    assert result == GrowthType.UNKNOWN


def test_unknown_empty_windows() -> None:
    """Empty windows list → UNKNOWN."""
    result = classify_growth_type([])
    assert result == GrowthType.UNKNOWN


def test_unknown_single_window() -> None:
    """Single window → UNKNOWN (need at least 2)."""
    windows = [VelocityWindow(0, 12, 1)]
    result = classify_growth_type(windows)
    assert result == GrowthType.UNKNOWN


def test_growth_two_windows_strong_rise() -> None:
    """Two windows, recent >= mid * 1.5 → GROWTH."""
    windows = [
        VelocityWindow(0, 12, 15),
        VelocityWindow(12, 24, 9),
    ]
    result = classify_growth_type(windows)
    assert result == GrowthType.GROWTH


def test_spike_mid_zero() -> None:
    """mid = 0 should be treated as max(mid, 1) = 1 → SPIKE if recent >= 3."""
    windows = [
        VelocityWindow(0, 12, 10),
        VelocityWindow(12, 24, 0),
    ]
    result = classify_growth_type(windows)
    assert result == GrowthType.SPIKE


# ---------------------------------------------------------------------------
# compute_silhouette_score tests
# ---------------------------------------------------------------------------


def test_silhouette_empty_clusters() -> None:
    """Empty cluster list → None."""
    result = compute_silhouette_score([])
    assert result is None


def test_silhouette_single_cluster() -> None:
    """Single cluster → None (need >= 2 clusters)."""
    item = ClusterItem(item_id="a", text="test")
    cluster = Cluster(cluster_id="c0", representative=item)
    result = compute_silhouette_score([cluster])
    assert result is None


def test_silhouette_no_embeddings() -> None:
    """Two clusters but no embeddings → None."""
    item1 = ClusterItem(item_id="a", text="hello")
    item2 = ClusterItem(item_id="b", text="world")
    c1 = Cluster(cluster_id="c0", representative=item1)
    c2 = Cluster(cluster_id="c1", representative=item2)
    result = compute_silhouette_score([c1, c2], embeddings=None)
    assert result is None


def test_silhouette_insufficient_items() -> None:
    """Two clusters but fewer than 4 total items → None."""
    item1 = ClusterItem(item_id="a", text="hello")
    item2 = ClusterItem(item_id="b", text="world")
    c1 = Cluster(cluster_id="c0", representative=item1)
    c2 = Cluster(cluster_id="c1", representative=item2)
    # Only 2 embeddings — below threshold of 4
    result = compute_silhouette_score([c1, c2], embeddings=[[1.0, 0.0], [0.0, 1.0]])
    assert result is None
