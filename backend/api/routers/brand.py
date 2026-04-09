"""Brand Monitoring API — Business+ plan-gated endpoints.

RULE 02: asyncpg $1/$2 parameterization only.
RULE 06: try/except + structlog on all handlers.
RULE 07: type hints on all functions.
RULE 08: Plan gate server-side via require_plan("business", status_code=402).
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request

from backend.api.schemas.brand import (
    BrandCreateRequest,
    BrandCreateResponse,
    BrandItem,
    BrandListResponse,
    BrandMentionItem,
    BrandMonitorResponse,
)
from backend.auth.dependencies import PLAN_LEVEL, CurrentUser, require_plan
from backend.common.audit import write_audit_log
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode, http_error
from backend.processor.algorithms.brand_monitor import monitor_brand

router = APIRouter(prefix="/brand", tags=["brand"])
logger = structlog.get_logger(__name__)

_BUSINESS_BRAND_LIMIT = 3


@router.get("", response_model=BrandListResponse)
@handle_errors(log_event="brand_list_failed")
async def list_brands(
    request: Request,
    current_user: CurrentUser = Depends(require_plan("business", status_code=402)),  # noqa: B008
) -> BrandListResponse:
    """List all active brand monitors for the authenticated Business+ user."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::text, brand_name, keywords, is_active,
                   slack_webhook, last_alerted_at, created_at, updated_at
            FROM brand_monitor
            WHERE user_id = $1::uuid
              AND is_active = TRUE
            ORDER BY created_at DESC
            """,
            current_user.user_id,
        )
    brands = [
        BrandItem(
            id=row["id"],
            brand_name=row["brand_name"],
            keywords=list(row["keywords"] or []),
            is_active=row["is_active"],
            slack_webhook=row["slack_webhook"],
            last_alerted_at=row["last_alerted_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]
    return BrandListResponse(brands=brands)


@router.get("/{name}/monitor", response_model=BrandMonitorResponse)
@handle_errors(log_event="brand_monitor_endpoint_failed")
async def get_brand_monitor(
    name: str,
    request: Request,
    current_user: CurrentUser = Depends(require_plan("business", status_code=402)),  # noqa: B008
) -> BrandMonitorResponse:
    """Run brand sentiment crisis monitor for a registered brand.

    Returns Z-score analysis against the 24-hour baseline using cached data.
    Supply fresh texts via POST /brand/{name}/monitor for live analysis.
    """
    pool = request.app.state.db_pool
    result = await monitor_brand(
        pool=pool,
        user_id=current_user.user_id,
        brand_name=name,
        texts=[],
    )
    return BrandMonitorResponse(
        brand_name=result.brand_name,
        current_score=result.current_score,
        mean_24h=result.mean_24h,
        std_24h=result.std_24h,
        z_score=result.z_score,
        alert_threshold=result.alert_threshold,
        is_crisis=result.is_crisis,
        label=result.label,
        cached=result.cached,
        mentions=[BrandMentionItem(**m) for m in result.mentions],
    )


@router.post("", response_model=BrandCreateResponse, status_code=201)
@handle_errors(log_event="brand_create_failed")
async def create_brand(
    body: BrandCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_plan("business", status_code=402)),  # noqa: B008
) -> BrandCreateResponse:
    """Register a new brand monitor.

    Business plan: maximum 3 brands. Enterprise: unlimited.
    """
    pool = request.app.state.db_pool

    user_level = PLAN_LEVEL.get(current_user.plan, 0)
    is_enterprise = user_level >= PLAN_LEVEL["enterprise"]

    async with pool.acquire() as conn:
        if not is_enterprise:
            existing_count: int = await conn.fetchval(
                """
                SELECT COUNT(*) FROM brand_monitor
                WHERE user_id = $1::uuid AND is_active = TRUE
                """,
                current_user.user_id,
            )
            if existing_count >= _BUSINESS_BRAND_LIMIT:
                raise http_error(
                    ErrorCode.QUOTA_EXCEEDED,
                    f"Business plan allows up to {_BUSINESS_BRAND_LIMIT} brands. "
                    "Upgrade to Enterprise for unlimited brands.",
                    status_code=402,
                )

        duplicate = await conn.fetchval(
            """
            SELECT id FROM brand_monitor
            WHERE user_id = $1::uuid AND brand_name = $2 AND is_active = TRUE
            """,
            current_user.user_id,
            body.brand_name,
        )
        if duplicate is not None:
            raise http_error(
                ErrorCode.DUPLICATE_ENTRY,
                f"Brand '{body.brand_name}' is already registered.",
                status_code=409,
            )

        row = await conn.fetchrow(
            """
            INSERT INTO brand_monitor (user_id, brand_name, keywords, slack_webhook)
            VALUES ($1::uuid, $2, $3::text[], $4)
            RETURNING id::text, brand_name, keywords, slack_webhook, created_at
            """,
            current_user.user_id,
            body.brand_name,
            body.keywords,
            body.slack_webhook,
        )

        await write_audit_log(
            conn,
            user_id=current_user.user_id,
            action="brand_create",
            target_type="brand_monitor",
            target_id=row["id"],
            detail={"brand_name": body.brand_name},
        )

    logger.info(
        "brand_created",
        user_id=current_user.user_id,
        brand_name=body.brand_name,
    )
    return BrandCreateResponse(
        id=row["id"],
        brand_name=row["brand_name"],
        keywords=list(row["keywords"] or []),
        slack_webhook=row["slack_webhook"],
        created_at=row["created_at"],
    )


@router.delete("/{name}", status_code=204, response_model=None)
@handle_errors(log_event="brand_delete_failed")
async def delete_brand(
    name: str,
    request: Request,
    current_user: CurrentUser = Depends(require_plan("business", status_code=402)),  # noqa: B008
) -> None:
    """Soft-delete (deactivate) a brand monitor.

    Sets is_active = FALSE; data is retained for audit purposes.
    """
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        deleted_id = await conn.fetchval(
            """
            UPDATE brand_monitor
            SET is_active = FALSE, updated_at = now()
            WHERE user_id = $1::uuid
              AND brand_name = $2
              AND is_active = TRUE
            RETURNING id::text
            """,
            current_user.user_id,
            name,
        )
        if deleted_id is None:
            raise http_error(
                ErrorCode.NOT_FOUND,
                f"Brand '{name}' not found.",
                status_code=404,
            )

        await write_audit_log(
            conn,
            user_id=current_user.user_id,
            action="brand_delete",
            target_type="brand_monitor",
            target_id=deleted_id,
            detail={"brand_name": name},
        )

    logger.info(
        "brand_deleted",
        user_id=current_user.user_id,
        brand_name=name,
    )
