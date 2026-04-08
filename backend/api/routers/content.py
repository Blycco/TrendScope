"""POST /api/v1/content/ideas — Pro+ plan-gated content idea generation."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request

from backend.api.schemas.content import ContentIdeaItem, ContentIdeaRequest, ContentIdeaResponse
from backend.auth.dependencies import CurrentUser, require_plan
from backend.common.decorators import handle_errors
from backend.processor.algorithms.content_ideas import ContentIdeasEngine
from backend.processor.shared.ai_config import get_ai_config

router = APIRouter(prefix="/content", tags=["content"])
logger = structlog.get_logger(__name__)


@router.post("/ideas", response_model=ContentIdeaResponse)
@handle_errors(log_event="content_ideas_generation_failed")
async def generate_content_ideas(
    body: ContentIdeaRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_plan("pro", status_code=402)),  # noqa: B008
) -> ContentIdeaResponse:
    """Generate role-tailored content ideas for a keyword, gated to Pro+ users."""
    pool = request.app.state.db_pool
    ai_config = await get_ai_config(pool)

    role = (
        current_user.role
        if current_user.role in {"marketer", "creator", "owner", "general"}
        else "general"
    )

    engine = ContentIdeasEngine(pool, ai_config)
    result = await engine.generate(
        keyword=body.keyword,
        role=role,
        sources=body.sources,
    )

    ideas = [ContentIdeaItem(**item) for item in result["ideas"]]
    return ContentIdeaResponse(ideas=ideas, cached=result["cached"])
