"""Classify a trend into one of five status labels based on score dynamics."""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

VALID_STATUSES = ("exploding", "rising", "stable", "declining", "peaked")


def classify_trend_status(
    current_score: float,
    prev_score: float | None,
    direction: str | None,
) -> str:
    """Return a status label for a trend group.

    Parameters
    ----------
    current_score:
        The current trend score (0–100 scale).
    prev_score:
        The previous trend score, or ``None`` if unavailable.
    direction:
        Direction string from the velocity calculation (``"up"``, ``"down"``,
        ``"rising"``, ``"declining"``, ``"steady"``, or ``None``).

    Returns
    -------
    str
        One of ``"exploding"``, ``"rising"``, ``"stable"``, ``"declining"``,
        ``"peaked"``.
    """
    try:
        dir_up = direction in ("up", "rising")
        dir_down = direction in ("down", "declining")

        if prev_score is not None and prev_score > 0:
            change_ratio = (current_score - prev_score) / prev_score
        else:
            change_ratio = 0.0

        # exploding: score increase > 50% or score > 80 with direction "up"
        if change_ratio > 0.5 or (current_score > 80 and dir_up):
            return "exploding"

        # rising: score increase > 10% or direction "up"
        if change_ratio > 0.1 or dir_up:
            return "rising"

        # peaked: score decrease < 10% but score > 60
        if change_ratio > -0.1 and current_score > 60 and (dir_down or change_ratio < 0):
            return "peaked"

        # declining: score decrease > 10% or direction "down"
        if change_ratio < -0.1 or dir_down:
            return "declining"

        # stable: everything else
        return "stable"

    except Exception:
        logger.exception("trend_status_classify_error")
        return "stable"
