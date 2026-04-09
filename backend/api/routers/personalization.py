"""GET/PUT /api/v1/personalization — per-user content personalization settings."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request

from backend.api.schemas.personalization import (
    BehaviorStatsResponse,
    PersonalizationResponse,
    PersonalizationUpdate,
)
from backend.auth.dependencies import CurrentUser, require_auth
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.events import get_behavior_stats
from backend.db.queries.personalization import get_personalization, upsert_personalization

router = APIRouter(prefix="/personalization", tags=["personalization"])
logger = structlog.get_logger(__name__)


@router.get("", response_model=PersonalizationResponse)
@handle_errors(log_event="get_personalization_failed")
async def get_my_personalization(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> PersonalizationResponse:
    """Return personalization settings for the authenticated user."""
    pool = request.app.state.db_pool
    row = await get_personalization(pool, user_id=current_user.user_id)
    if row is None:
        return PersonalizationResponse(category_weights={}, locale_ratio=0.5)
    return PersonalizationResponse(
        category_weights=dict(row["category_weights"]),
        locale_ratio=row["locale_ratio"],
    )


@router.put("", response_model=PersonalizationResponse)
@handle_errors(log_event="update_personalization_failed")
async def update_my_personalization(
    body: PersonalizationUpdate,
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> PersonalizationResponse:
    """Create or update personalization settings for the authenticated user."""
    pool = request.app.state.db_pool
    await upsert_personalization(
        pool,
        user_id=current_user.user_id,
        category_weights=body.category_weights,
        locale_ratio=body.locale_ratio,
    )
    logger.info(
        "personalization_updated",
        user_id=current_user.user_id,
        locale_ratio=body.locale_ratio,
    )
    return PersonalizationResponse(
        category_weights=body.category_weights,
        locale_ratio=body.locale_ratio,
    )


def _compute_suggested_weights(category_counts: dict[str, int]) -> dict[str, float]:
    """Derive category weights (0.5–2.0) from behavior counts."""
    if not category_counts:
        return {}
    max_count = max(category_counts.values())
    if max_count == 0:
        return {}
    return {cat: round(0.5 + 1.5 * (cnt / max_count), 2) for cat, cnt in category_counts.items()}


@router.get("/behavior", response_model=BehaviorStatsResponse)
@handle_errors(log_event="get_behavior_analysis_failed")
async def get_behavior_analysis(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> BehaviorStatsResponse:
    """Return aggregated behavior stats and suggested weights for the authenticated user."""
    pool = request.app.state.db_pool
    stats = await get_behavior_stats(pool, user_id=current_user.user_id)
    suggested = _compute_suggested_weights(stats["category_counts"])
    return BehaviorStatsResponse(
        category_counts=stats["category_counts"],
        total_events=stats["total_events"],
        action_counts=stats["action_counts"],
        suggested_weights=suggested,
    )


@router.post("/behavior/apply", response_model=PersonalizationResponse)
@handle_errors(log_event="apply_behavior_weights_failed")
async def apply_behavior_weights(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> PersonalizationResponse:
    """Apply behavior-derived weights to user personalization settings."""
    pool = request.app.state.db_pool
    stats = await get_behavior_stats(pool, user_id=current_user.user_id)
    suggested = _compute_suggested_weights(stats["category_counts"])
    if not suggested:
        raise http_error(
            ErrorCode.VALIDATION_ERROR,
            "Not enough behavior data to generate weights",
            status_code=400,
        )
    current = await get_personalization(pool, user_id=current_user.user_id)
    locale_ratio = current["locale_ratio"] if current else 0.5
    await upsert_personalization(
        pool,
        user_id=current_user.user_id,
        category_weights=suggested,
        locale_ratio=locale_ratio,
    )
    logger.info(
        "behavior_weights_applied",
        user_id=current_user.user_id,
        weights=suggested,
    )
    return PersonalizationResponse(
        category_weights=suggested,
        locale_ratio=locale_ratio,
    )
