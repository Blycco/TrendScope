"""Admin stopword CRUD + cache reload endpoints. (RULE 06, 07, 08)"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from backend.auth.dependencies import CurrentUser, require_admin_role
from backend.common.audit import log_audit
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode
from backend.processor.shared.keyword_extractor import reload_stopword_cache

router = APIRouter(prefix="/stopwords", tags=["admin-stopwords"])
logger = structlog.get_logger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────


class StopwordItem(BaseModel):
    id: str
    word: str
    locale: str
    is_active: bool
    source: str
    created_at: str


class StopwordListResponse(BaseModel):
    items: list[StopwordItem]
    total: int


class StopwordCreateRequest(BaseModel):
    word: str = Field(..., min_length=1, max_length=100)
    locale: str = Field(default="ko", pattern=r"^(ko|en)$")


class ReloadResponse(BaseModel):
    ok: bool


# ── Helpers ───────────────────────────────────────────────────────────────────


def _row_to_item(row: dict) -> StopwordItem:
    return StopwordItem(
        id=str(row["id"]),
        word=row["word"],
        locale=row["locale"],
        is_active=row["is_active"],
        source=row["source"],
        created_at=row["created_at"].isoformat(),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", response_model=StopwordListResponse)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to list stopwords",
    status_code=500,
    log_event="admin_stopwords_list_failed",
)
async def list_stopwords(
    request: Request,
    locale: str = Query(default="ko"),
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> StopwordListResponse:
    """불용어 목록 조회."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        total: int = await conn.fetchval(
            "SELECT COUNT(*) FROM stopword WHERE locale = $1",
            locale,
        )
        rows = await conn.fetch(
            """
            SELECT id, word, locale, is_active, source, created_at
            FROM stopword
            WHERE locale = $1
            ORDER BY word ASC
            """,
            locale,
        )
    return StopwordListResponse(
        items=[_row_to_item(dict(r)) for r in rows],
        total=total,
    )


@router.post("", response_model=StopwordItem, status_code=201)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to create stopword",
    status_code=500,
    log_event="admin_stopword_create_failed",
)
async def create_stopword(
    body: StopwordCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> StopwordItem:
    """불용어 추가."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO stopword (word, locale, source)
            VALUES ($1, $2, 'manual')
            ON CONFLICT (word, locale) DO NOTHING
            RETURNING id, word, locale, is_active, source, created_at
            """,
            body.word,
            body.locale,
        )

    await log_audit(
        pool,
        user_id=current_user.user_id,
        action="stopword_create",
        target_type="stopword",
        target_id=str(row["id"]) if row else None,
        ip_address=str(request.client.host) if request.client else None,
        detail={"word": body.word, "locale": body.locale},
    )
    logger.info("stopword_created", word=body.word, by=current_user.user_id)
    return _row_to_item(dict(row))


@router.delete("/{sw_id}", status_code=204, response_model=None)
@handle_errors(
    error_code=ErrorCode.DB_ERROR,
    message="Failed to delete stopword",
    status_code=500,
    log_event="admin_stopword_delete_failed",
)
async def delete_stopword(
    sw_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role(admin_only=True)),  # noqa: B008
) -> None:
    """불용어 삭제."""
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM stopword WHERE id = $1", sw_id)

    await log_audit(
        pool,
        user_id=current_user.user_id,
        action="stopword_delete",
        target_type="stopword",
        target_id=sw_id,
        ip_address=str(request.client.host) if request.client else None,
    )
    logger.info("stopword_deleted", id=sw_id, by=current_user.user_id)


@router.post("/reload", response_model=ReloadResponse)
@handle_errors(
    error_code=ErrorCode.INTERNAL_ERROR,
    message="Failed to reload stopword cache",
    status_code=500,
    log_event="admin_stopwords_reload_failed",
)
async def reload_stopwords_cache(
    request: Request,
    current_user: CurrentUser = Depends(require_admin_role()),  # noqa: B008
) -> ReloadResponse:
    """Redis 불용어 캐시 무효화."""
    await reload_stopword_cache()
    logger.info("stopword_cache_reloaded", by=current_user.user_id)
    return ReloadResponse(ok=True)
