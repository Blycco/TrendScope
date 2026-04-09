"""Admin filter-keyword CRUD + cache reload endpoints. (RULE 06, 07, 08)"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.audit import log_audit
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode
from backend.processor.shared.spam_filter import reload_filter_cache

router = APIRouter(prefix="/filter-keywords", tags=["admin-filter-keywords"])
logger = structlog.get_logger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────


class FilterKeywordItem(BaseModel):
    id: str
    keyword: str
    category: str
    source: str
    is_active: bool
    confidence: float
    created_at: str
    updated_at: str


class FilterKeywordListResponse(BaseModel):
    items: list[FilterKeywordItem]
    total: int


class FilterKeywordCreateRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., pattern=r"^(ad|gambling|adult|obituary|irrelevant|custom)$")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class FilterKeywordPatchRequest(BaseModel):
    is_active: bool | None = None
    category: str | None = Field(
        default=None,
        pattern=r"^(ad|gambling|adult|obituary|irrelevant|custom)$",
    )


class ReloadResponse(BaseModel):
    ok: bool


# ── Helpers ───────────────────────────────────────────────────────────────────


def _row_to_item(row: dict) -> FilterKeywordItem:
    return FilterKeywordItem(
        id=str(row["id"]),
        keyword=row["keyword"],
        category=row["category"],
        source=row["source"],
        is_active=row["is_active"],
        confidence=float(row["confidence"]),
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", response_model=FilterKeywordListResponse)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to list filter keywords",
    status_code=500,
    log_event="admin_filter_kw_list_failed",
)
async def list_filter_keywords(
    request: Request,
    category: str | None = Query(default=None),
    source: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> FilterKeywordListResponse:
    """필터 키워드 목록 조회."""
    pool = request.app.state.db_pool
    clauses: list[str] = []
    params: list[object] = []
    idx = 1

    if category is not None:
        clauses.append(f"category = ${idx}")
        params.append(category)
        idx += 1
    if source is not None:
        clauses.append(f"source = ${idx}")
        params.append(source)
        idx += 1
    if is_active is not None:
        clauses.append(f"is_active = ${idx}")
        params.append(is_active)
        idx += 1

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    async with pool.acquire() as conn:
        total: int = await conn.fetchval(
            f"SELECT COUNT(*) FROM filter_keyword {where}",  # noqa: S608
            *params,
        )
        rows = await conn.fetch(
            f"""
            SELECT id, keyword, category, source, is_active, confidence,
                   created_at, updated_at
            FROM filter_keyword {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,  # noqa: S608
            *params,
            limit,
            offset,
        )

    return FilterKeywordListResponse(
        items=[_row_to_item(dict(r)) for r in rows],
        total=total,
    )


@router.post("", response_model=FilterKeywordItem, status_code=201)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to create filter keyword",
    status_code=500,
    log_event="admin_filter_kw_create_failed",
)
async def create_filter_keyword(
    body: FilterKeywordCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> FilterKeywordItem:
    """필터 키워드 추가."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO filter_keyword (keyword, category, source, confidence)
            VALUES ($1, $2, 'manual', $3)
            ON CONFLICT (keyword) DO NOTHING
            RETURNING id, keyword, category, source, is_active,
                      confidence, created_at, updated_at
            """,
            body.keyword,
            body.category,
            body.confidence,
        )

    await log_audit(
        pool,
        user_id=current_user.user_id,
        action="filter_keyword_create",
        target_type="filter_keyword",
        target_id=str(row["id"]) if row else None,
        ip_address=str(request.client.host) if request.client else None,
        detail={"keyword": body.keyword, "category": body.category},
    )
    logger.info("filter_keyword_created", keyword=body.keyword, by=current_user.user_id)
    return _row_to_item(dict(row))


@router.patch("/{kw_id}", response_model=FilterKeywordItem)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to update filter keyword",
    status_code=500,
    log_event="admin_filter_kw_patch_failed",
)
async def patch_filter_keyword(
    kw_id: str,
    body: FilterKeywordPatchRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> FilterKeywordItem:
    """is_active 토글 또는 category 변경."""
    pool = request.app.state.db_pool
    sets: list[str] = ["updated_at = now()"]
    params: list[object] = []
    idx = 1

    if body.is_active is not None:
        sets.append(f"is_active = ${idx}")
        params.append(body.is_active)
        idx += 1
    if body.category is not None:
        sets.append(f"category = ${idx}")
        params.append(body.category)
        idx += 1

    params.append(kw_id)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE filter_keyword SET {', '.join(sets)}
            WHERE id = ${idx}
            RETURNING id, keyword, category, source, is_active,
                      confidence, created_at, updated_at
            """,  # noqa: S608
            *params,
        )

    await log_audit(
        pool,
        user_id=current_user.user_id,
        action="filter_keyword_patch",
        target_type="filter_keyword",
        target_id=kw_id,
        ip_address=str(request.client.host) if request.client else None,
        detail=body.model_dump(exclude_none=True),
    )
    logger.info("filter_keyword_patched", id=kw_id, by=current_user.user_id)
    return _row_to_item(dict(row))


@router.delete("/{kw_id}", status_code=204, response_model=None)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to delete filter keyword",
    status_code=500,
    log_event="admin_filter_kw_delete_failed",
)
async def delete_filter_keyword(
    kw_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role(admin_only=True)),  # noqa: B008
) -> None:
    """필터 키워드 삭제."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM filter_keyword WHERE id = $1", kw_id)

    await log_audit(
        pool,
        user_id=current_user.user_id,
        action="filter_keyword_delete",
        target_type="filter_keyword",
        target_id=kw_id,
        ip_address=str(request.client.host) if request.client else None,
    )
    logger.info("filter_keyword_deleted", id=kw_id, by=current_user.user_id)


@router.post("/{kw_id}/approve", response_model=FilterKeywordItem)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to approve filter keyword",
    status_code=500,
    log_event="admin_filter_kw_approve_failed",
)
async def approve_filter_keyword(
    kw_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> FilterKeywordItem:
    """AI 제안 키워드를 수동 승인 (is_active=TRUE, source='manual')."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE filter_keyword
            SET is_active = TRUE, source = 'manual', updated_at = now()
            WHERE id = $1
            RETURNING id, keyword, category, source, is_active,
                      confidence, created_at, updated_at
            """,
            kw_id,
        )

    await log_audit(
        pool,
        user_id=current_user.user_id,
        action="filter_keyword_approve",
        target_type="filter_keyword",
        target_id=kw_id,
        ip_address=str(request.client.host) if request.client else None,
    )
    logger.info("filter_keyword_approved", id=kw_id, by=current_user.user_id)
    return _row_to_item(dict(row))


@router.post("/reload", response_model=ReloadResponse)
@handle_errors(
    error_code=ErrorCode.INTERNAL_ERROR,
    message="Failed to reload filter keyword cache",
    status_code=500,
    log_event="admin_filter_kw_reload_failed",
)
async def reload_filter_keyword_cache(
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> ReloadResponse:
    """Redis 필터 키워드 캐시 무효화."""
    await reload_filter_cache()
    logger.info("filter_kw_cache_reloaded", by=current_user.user_id)
    return ReloadResponse(ok=True)
