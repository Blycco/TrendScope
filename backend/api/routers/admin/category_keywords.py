"""Admin category-keyword CRUD + cache reload endpoints. (RULE 06, 07, 08)"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.audit import log_audit
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode
from backend.processor.shared.config_loader import invalidate_cache

router = APIRouter(prefix="/category-keywords", tags=["admin-category-keywords"])
logger = structlog.get_logger(__name__)

_VALID_CATEGORIES = frozenset(
    {"sports", "tech", "economy", "entertainment", "science", "politics", "society", "general"}
)

# ── Schemas ──────────────────────────────────────────────────────────────────


class CategoryKeywordItem(BaseModel):
    id: str
    keyword: str
    category: str
    weight: float
    locale: str
    is_active: bool
    created_at: str


class CategoryKeywordListResponse(BaseModel):
    items: list[CategoryKeywordItem]
    total: int


class CategoryKeywordCreateRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)
    category: str
    weight: float = Field(default=1.0, ge=0.5, le=2.0)
    locale: str = Field(default="ko", pattern=r"^(ko|en)$")


class CategoryKeywordPatchRequest(BaseModel):
    weight: float = Field(..., ge=0.5, le=2.0)


class ReloadResponse(BaseModel):
    ok: bool


# ── Helpers ───────────────────────────────────────────────────────────────────


def _row_to_item(row: dict) -> CategoryKeywordItem:
    return CategoryKeywordItem(
        id=str(row["id"]),
        keyword=row["keyword"],
        category=row["category"],
        weight=float(row["weight"]),
        locale=row["locale"],
        is_active=row["is_active"],
        created_at=row["created_at"].isoformat(),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", response_model=CategoryKeywordListResponse)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to list category keywords",
    status_code=500,
    log_event="admin_cat_kw_list_failed",
)
async def list_category_keywords(
    request: Request,
    category: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> CategoryKeywordListResponse:
    """카테고리 키워드 목록 조회."""
    pool = request.app.state.db_pool
    if category is not None:
        async with pool.acquire() as conn:
            total: int = await conn.fetchval(
                "SELECT COUNT(*) FROM category_keyword WHERE category = $1",
                category,
            )
            rows = await conn.fetch(
                """
                SELECT id, keyword, category, weight, locale, is_active, created_at
                FROM category_keyword
                WHERE category = $1
                ORDER BY weight DESC, keyword ASC
                """,
                category,
            )
    else:
        async with pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM category_keyword")
            rows = await conn.fetch(
                """
                SELECT id, keyword, category, weight, locale, is_active, created_at
                FROM category_keyword
                ORDER BY category, weight DESC
                """
            )
    return CategoryKeywordListResponse(
        items=[_row_to_item(dict(r)) for r in rows],
        total=total,
    )


@router.post("", response_model=CategoryKeywordItem, status_code=201)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to create category keyword",
    status_code=500,
    log_event="admin_cat_kw_create_failed",
)
async def create_category_keyword(
    body: CategoryKeywordCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> CategoryKeywordItem:
    """카테고리 키워드 추가."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO category_keyword (keyword, category, weight, locale)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (keyword, category) DO NOTHING
            RETURNING id, keyword, category, weight, locale, is_active, created_at
            """,
            body.keyword,
            body.category,
            body.weight,
            body.locale,
        )

    await log_audit(
        pool,
        user_id=current_user.user_id,
        action="category_keyword_create",
        target_type="category_keyword",
        target_id=str(row["id"]) if row else None,
        ip_address=str(request.client.host) if request.client else None,
        detail={"keyword": body.keyword, "category": body.category, "weight": body.weight},
    )
    logger.info("category_keyword_created", keyword=body.keyword, by=current_user.user_id)
    return _row_to_item(dict(row))


@router.patch("/{kw_id}", response_model=CategoryKeywordItem)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to update category keyword",
    status_code=500,
    log_event="admin_cat_kw_patch_failed",
)
async def patch_category_keyword(
    kw_id: str,
    body: CategoryKeywordPatchRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> CategoryKeywordItem:
    """카테고리 키워드 weight 수정."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE category_keyword SET weight = $1
            WHERE id = $2
            RETURNING id, keyword, category, weight, locale, is_active, created_at
            """,
            body.weight,
            kw_id,
        )
    await log_audit(
        pool,
        user_id=current_user.user_id,
        action="category_keyword_patch",
        target_type="category_keyword",
        target_id=kw_id,
        ip_address=str(request.client.host) if request.client else None,
        detail={"weight": body.weight},
    )
    logger.info("category_keyword_patched", id=kw_id, by=current_user.user_id)
    return _row_to_item(dict(row))


@router.delete("/{kw_id}", status_code=204, response_model=None)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to delete category keyword",
    status_code=500,
    log_event="admin_cat_kw_delete_failed",
)
async def delete_category_keyword(
    kw_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role(admin_only=True)),  # noqa: B008
) -> None:
    """카테고리 키워드 삭제."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM category_keyword WHERE id = $1", kw_id)
    await log_audit(
        pool,
        user_id=current_user.user_id,
        action="category_keyword_delete",
        target_type="category_keyword",
        target_id=kw_id,
        ip_address=str(request.client.host) if request.client else None,
    )
    logger.info("category_keyword_deleted", id=kw_id, by=current_user.user_id)


@router.post("/reload", response_model=ReloadResponse)
@handle_errors(
    error_code=ErrorCode.INTERNAL_ERROR,
    message="Failed to reload category keyword cache",
    status_code=500,
    log_event="admin_cat_kw_reload_failed",
)
async def reload_category_keyword_cache(
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> ReloadResponse:
    """Redis 카테고리 키워드 캐시 무효화."""
    await invalidate_cache("category_kw")
    logger.info("category_kw_cache_reloaded", by=current_user.user_id)
    return ReloadResponse(ok=True)
