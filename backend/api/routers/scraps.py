"""Scrap endpoints: create, list, delete with plan gate. (RULE 08, RULE 17)"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from backend.api.schemas.scraps import ScrapCreate, ScrapListResponse, ScrapResponse
from backend.auth.dependencies import CurrentUser, require_auth
from backend.common.audit import write_audit_log
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.scraps import (
    create_scrap,
    delete_scrap,
    get_scrap_count,
    list_scraps,
)

router = APIRouter(prefix="/scraps", tags=["scraps"])
logger = structlog.get_logger(__name__)

_FREE_SCRAP_LIMIT = 50


@router.post("", response_model=ScrapResponse, status_code=201)
async def create_scrap_endpoint(
    body: ScrapCreate,
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> ScrapResponse:
    """Create a new scrap. Free plan limited to 50 scraps."""
    try:
        pool = request.app.state.db_pool

        # Plan gate: free plan limit
        count = await get_scrap_count(pool, user_id=current_user.user_id)
        if count >= _FREE_SCRAP_LIMIT and current_user.plan == "free":
            raise http_error(ErrorCode.PLAN_GATE, "Free plan limit: 50 scraps", status_code=403)

        row = await create_scrap(
            pool,
            user_id=current_user.user_id,
            item_type=body.item_type,
            item_id=body.item_id,
            user_tags=body.user_tags,
            memo=body.memo,
        )

        async with pool.acquire() as conn:
            await write_audit_log(
                conn,
                user_id=current_user.user_id,
                action="scrap_create",
                target_type="scrap",
                target_id=row["id"],
                ip_address=str(request.client.host) if request.client else None,
            )

        logger.info("scrap_created", user_id=current_user.user_id, scrap_id=row["id"])
        return ScrapResponse(
            id=row["id"],
            user_id=row["user_id"],
            item_type=row["item_type"],
            item_id=row["item_id"],
            user_tags=row["user_tags"],
            memo=row["memo"],
            created_at=row["created_at"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("create_scrap_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to create scrap", status_code=500) from exc


@router.get("", response_model=ScrapListResponse)
async def list_scraps_endpoint(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> ScrapListResponse:
    """List the authenticated user's scraps."""
    try:
        pool = request.app.state.db_pool
        rows = await list_scraps(pool, user_id=current_user.user_id, limit=limit, offset=offset)
        total = await get_scrap_count(pool, user_id=current_user.user_id)

        items = [
            ScrapResponse(
                id=r["id"],
                user_id=r["user_id"],
                item_type=r["item_type"],
                item_id=r["item_id"],
                user_tags=r["user_tags"],
                memo=r["memo"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
        return ScrapListResponse(items=items, total=total)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("list_scraps_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to list scraps", status_code=500) from exc


@router.delete("/{scrap_id}", status_code=204, response_class=Response)
async def delete_scrap_endpoint(
    scrap_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> Response:
    """Delete a scrap by ID (owner only)."""
    try:
        pool = request.app.state.db_pool
        deleted = await delete_scrap(pool, scrap_id=scrap_id, user_id=current_user.user_id)
        if not deleted:
            raise http_error(ErrorCode.NOT_FOUND, "Scrap not found", status_code=404)

        async with pool.acquire() as conn:
            await write_audit_log(
                conn,
                user_id=current_user.user_id,
                action="scrap_delete",
                target_type="scrap",
                target_id=scrap_id,
                ip_address=str(request.client.host) if request.client else None,
            )

        logger.info("scrap_deleted", user_id=current_user.user_id, scrap_id=scrap_id)
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("delete_scrap_failed", error=str(exc))
        raise http_error(ErrorCode.DB_ERROR, "Failed to delete scrap", status_code=500) from exc
