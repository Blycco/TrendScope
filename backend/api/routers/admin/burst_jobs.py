"""Admin burst job endpoints — log viewing + manual trigger. (RULE 06, RULE 07, RULE 08)"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.api.schemas.admin import BurstJobListResponse, BurstTriggerRequest
from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.errors import ErrorCode, http_error
from backend.jobs.burst_job import manual_burst_trigger

router = APIRouter(prefix="/burst-jobs", tags=["admin-burst-jobs"])
logger = structlog.get_logger(__name__)


@router.get("")
async def list_burst_jobs(
    request: Request,
    status: str | None = Query(default=None),
    trigger_source: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> BurstJobListResponse:
    """List burst job logs with optional filters."""
    try:
        pool = request.app.state.db_pool

        conditions: list[str] = []
        params: list[object] = []
        idx = 1

        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        if trigger_source:
            conditions.append(f"trigger_source = ${idx}")
            params.append(trigger_source)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_query = f"SELECT COUNT(*) FROM burst_job_log {where}"  # noqa: S608
        total = await pool.fetchval(count_query, *params)

        offset = (page - 1) * page_size
        data_query = (
            f"SELECT id, triggered_at, trigger_source, group_id, "  # noqa: S608
            f"keywords, threshold, early_trend_score, articles_found, "
            f"duration_ms, status, error_detail, completed_at "
            f"FROM burst_job_log {where} "
            f"ORDER BY triggered_at DESC "
            f"LIMIT ${idx} OFFSET ${idx + 1}"
        )
        params.extend([page_size, offset])

        rows = await pool.fetch(data_query, *params)

        items = [
            {
                "id": row["id"],
                "triggered_at": (row["triggered_at"].isoformat() if row["triggered_at"] else None),
                "trigger_source": row["trigger_source"],
                "group_id": str(row["group_id"]) if row["group_id"] else None,
                "keywords": list(row["keywords"]) if row["keywords"] else [],
                "threshold": row["threshold"],
                "early_trend_score": row["early_trend_score"],
                "articles_found": row["articles_found"],
                "duration_ms": row["duration_ms"],
                "status": row["status"],
                "error_detail": row["error_detail"],
                "completed_at": (row["completed_at"].isoformat() if row["completed_at"] else None),
            }
            for row in rows
        ]

        return BurstJobListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_list_burst_jobs_failed", error=str(exc))
        raise http_error(
            ErrorCode.DB_ERROR,
            "Failed to list burst jobs",
            status_code=500,
        ) from exc


@router.post("/trigger")
async def trigger_burst_job(
    body: BurstTriggerRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> dict:
    """Manually trigger a burst crawl with specified keywords.

    Rate limited: max 1 burst per 30 minutes (returns 429 if locked).
    """
    try:
        pool = request.app.state.db_pool
        result = await manual_burst_trigger(
            pool,
            keywords=body.keywords,
            locale=body.locale,
        )

        if not result.get("success") and result.get("error") == "rate_limited":
            raise http_error(
                ErrorCode.QUOTA_EXCEEDED,
                "Burst job rate limited (max 1 per 30 minutes)",
                status_code=429,
            )

        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("admin_trigger_burst_failed", error=str(exc))
        raise http_error(
            ErrorCode.DB_ERROR,
            "Failed to trigger burst job",
            status_code=500,
        ) from exc
