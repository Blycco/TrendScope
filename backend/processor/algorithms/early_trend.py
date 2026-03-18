"""Early trend score computation: burst + velocity + source diversity. (RULE 07: type hints)"""

from __future__ import annotations

from backend.processor.algorithms.burst import BurstResult

# --- Formula weights (algorithms.md) ---
_BURST_WEIGHT: float = 0.5
_VELOCITY_WEIGHT: float = 0.3
_SOURCE_DIVERSITY_WEIGHT: float = 0.2


def compute_early_trend_score(
    burst_result: BurstResult,
    velocity: float,
    source_diversity: float,
) -> float:
    """Compute early trend score from burst detection result.

    Formula: 0.5 * burst_score + 0.3 * velocity + 0.2 * source_diversity
    All inputs normalized to [0, 1], output clamped to [0, 1].

    Args:
        burst_result: BurstResult from detect_burst()
        velocity: Rate of growth normalized to [0, 1]
        source_diversity: Source diversity score normalized to [0, 1]
            (e.g. num_unique_sources / max_expected_sources)

    Returns:
        Early trend score in [0, 1]
    """
    score = (
        _BURST_WEIGHT * burst_result.score
        + _VELOCITY_WEIGHT * velocity
        + _SOURCE_DIVERSITY_WEIGHT * source_diversity
    )
    return max(0.0, min(1.0, score))
