"""POST /api/v1/trends/share and GET /api/v1/shared/{token} endpoints. (RULE 08, RULE 11)"""

from __future__ import annotations

import secrets

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.auth.dependencies import CurrentUser, require_plan
from backend.common.errors import ErrorCode, error_response
from backend.db.queries.shares import create_shared_link, get_shared_link_by_token

router = APIRouter(tags=["shares"])
logger = structlog.get_logger(__name__)

_TOKEN_BYTES = 32


class ShareCreateRequest(BaseModel):
    payload: dict = {}


class ShareCreateResponse(BaseModel):
    token: str
    share_url: str
    expires_at: str


class SharedLinkResponse(BaseModel):
    token: str
    payload: dict
    expires_at: str
    created_at: str


@router.post("/trends/share", response_model=ShareCreateResponse)
async def create_share_link(
    body: ShareCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_plan("business")),  # noqa: B008
) -> JSONResponse:
    """Generate a 24-hour sharing token for a trend snapshot. Requires Business+ plan."""
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    try:
        pool = request.app.state.db_pool
        row = await create_shared_link(
            pool,
            token=token,
            user_id=current_user.user_id,
            payload=body.payload,
        )
        logger.info(
            "share_link_created",
            user_id=current_user.user_id,
            token=token,
        )
    except Exception as exc:
        logger.error("share_link_create_failed", error=str(exc))
        return error_response(ErrorCode.DB_ERROR, "Failed to create sharing link", status_code=500)

    return JSONResponse(
        status_code=201,
        content={
            "token": row["token"],
            "share_url": f"/shared/{row['token']}",
            "expires_at": row["expires_at"].isoformat(),
        },
    )


@router.get("/shared/{token}", response_model=SharedLinkResponse)
async def get_shared_link(
    token: str,
    request: Request,
) -> JSONResponse:
    """Retrieve a shared trend snapshot by token. No authentication required. Expires after 24h."""
    try:
        pool = request.app.state.db_pool
        row = await get_shared_link_by_token(pool, token=token)
    except Exception as exc:
        logger.error("get_shared_link_failed", error=str(exc))
        return error_response(ErrorCode.DB_ERROR, "Failed to fetch sharing link", status_code=500)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": ErrorCode.NOT_FOUND.value,
                "message": "Shared link not found or expired",
            },
        )

    logger.info("share_link_accessed", token=token)
    return JSONResponse(
        content={
            "token": row["token"],
            "payload": dict(row["payload"]),
            "expires_at": row["expires_at"].isoformat(),
            "created_at": row["created_at"].isoformat(),
        }
    )
