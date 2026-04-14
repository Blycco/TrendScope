"""Notification settings and keyword alert endpoints. (RULE 08, RULE 17)"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request

from backend.api.schemas.notifications import (
    KeywordAlertUpdate,
    KeywordCreateRequest,
    KeywordResponse,
    KeywordsResponse,
    NotificationSettingResponse,
    NotificationSettingsResponse,
    NotificationSettingUpdate,
)
from backend.auth.dependencies import PLAN_LEVEL, CurrentUser, require_auth
from backend.common.decorators import handle_errors
from backend.common.errors import ErrorCode, http_error
from backend.db.queries.notification_keywords import (
    count_keywords_for_user,
    delete_keyword,
    get_keywords_for_user,
    insert_keyword,
    update_keyword_alerts,
)
from backend.db.queries.notifications import (
    get_notification_settings,
    upsert_notification_setting,
)

_PRO_KEYWORD_LIMIT = 5

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = structlog.get_logger(__name__)


@router.get("/settings", response_model=NotificationSettingsResponse)
@handle_errors(log_event="get_notification_settings_failed")
async def get_settings(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> NotificationSettingsResponse:
    """Return all notification settings for the authenticated user."""
    pool = request.app.state.db_pool
    rows = await get_notification_settings(pool, user_id=current_user.user_id)
    return NotificationSettingsResponse(
        settings=[
            NotificationSettingResponse(
                id=row["id"],
                user_id=row["user_id"],
                type=row["type"],
                channel=row["channel"],
                is_enabled=row["is_enabled"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]
    )


@router.put("/settings", response_model=NotificationSettingsResponse)
@handle_errors(log_event="update_notification_settings_failed")
async def update_settings(
    body: NotificationSettingUpdate,
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> NotificationSettingsResponse:
    """Create or update a notification setting for the authenticated user."""
    pool = request.app.state.db_pool
    await upsert_notification_setting(
        pool,
        user_id=current_user.user_id,
        notification_type=body.type,
        channel=body.channel,
        is_enabled=body.is_enabled,
    )
    rows = await get_notification_settings(pool, user_id=current_user.user_id)
    logger.info(
        "notification_setting_updated",
        user_id=current_user.user_id,
        type=body.type,
        channel=body.channel,
    )
    return NotificationSettingsResponse(
        settings=[
            NotificationSettingResponse(
                id=row["id"],
                user_id=row["user_id"],
                type=row["type"],
                channel=row["channel"],
                is_enabled=row["is_enabled"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]
    )


@router.get("/keywords", response_model=KeywordsResponse)
@handle_errors(log_event="list_keywords_failed")
async def list_keywords(
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> KeywordsResponse:
    """Return all keyword alerts for the authenticated user. Requires Pro+ plan."""
    if PLAN_LEVEL.get(current_user.plan, 0) < PLAN_LEVEL["pro"]:
        raise http_error(
            ErrorCode.PLAN_GATE,
            "Keyword alerts require Pro plan or above",
            status_code=403,
        )
    pool = request.app.state.db_pool
    rows = await get_keywords_for_user(pool, user_id=current_user.user_id)
    return KeywordsResponse(
        keywords=[
            KeywordResponse(
                id=row["id"],
                user_id=row["user_id"],
                keyword=row["keyword"],
                alert_surge=row["alert_surge"],
                alert_daily=row["alert_daily"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
    )


@router.post("/keywords", response_model=KeywordResponse, status_code=201)
@handle_errors(log_event="add_keyword_failed")
async def add_keyword(
    body: KeywordCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> KeywordResponse:
    """Add a keyword alert. Pro: max 5 keywords. Business+: unlimited."""
    user_level = PLAN_LEVEL.get(current_user.plan, 0)
    if user_level < PLAN_LEVEL["pro"]:
        raise http_error(
            ErrorCode.PLAN_GATE,
            "Keyword alerts require Pro plan or above",
            status_code=403,
        )
    pool = request.app.state.db_pool

    if user_level < PLAN_LEVEL["business"]:
        count = await count_keywords_for_user(pool, user_id=current_user.user_id)
        if count >= _PRO_KEYWORD_LIMIT:
            raise http_error(
                ErrorCode.QUOTA_EXCEEDED,
                "Pro plan allows up to 5 keyword alerts",
                status_code=403,
            )

    row = await insert_keyword(pool, user_id=current_user.user_id, keyword=body.keyword)
    logger.info("keyword_added", user_id=current_user.user_id, keyword=body.keyword)
    return KeywordResponse(
        id=row["id"],
        user_id=row["user_id"],
        keyword=row["keyword"],
        alert_surge=row["alert_surge"],
        alert_daily=row["alert_daily"],
        created_at=row["created_at"],
    )


@router.patch("/keywords/{keyword_id}", response_model=KeywordResponse)
@handle_errors(log_event="update_keyword_alerts_failed")
async def patch_keyword_alerts(
    keyword_id: str,
    body: KeywordAlertUpdate,
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> KeywordResponse:
    """Update per-keyword alert toggles (surge / daily). Owner only."""
    pool = request.app.state.db_pool
    row = await update_keyword_alerts(
        pool,
        user_id=current_user.user_id,
        keyword_id=keyword_id,
        alert_surge=body.alert_surge,
        alert_daily=body.alert_daily,
    )
    if row is None:
        raise http_error(ErrorCode.NOT_FOUND, "Keyword not found", status_code=404)
    logger.info(
        "keyword_alerts_updated",
        user_id=current_user.user_id,
        keyword_id=keyword_id,
        alert_surge=body.alert_surge,
        alert_daily=body.alert_daily,
    )
    return KeywordResponse(
        id=row["id"],
        user_id=row["user_id"],
        keyword=row["keyword"],
        alert_surge=row["alert_surge"],
        alert_daily=row["alert_daily"],
        created_at=row["created_at"],
    )


@router.delete("/keywords/{keyword_id}", status_code=204, response_model=None)
@handle_errors(log_event="remove_keyword_failed")
async def remove_keyword(
    keyword_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_auth),  # noqa: B008
) -> None:
    """Delete a keyword alert by id. Only the owner may delete their own keywords."""
    pool = request.app.state.db_pool
    deleted = await delete_keyword(pool, user_id=current_user.user_id, keyword_id=keyword_id)
    if not deleted:
        raise http_error(ErrorCode.NOT_FOUND, "Keyword not found", status_code=404)
    logger.info("keyword_deleted", user_id=current_user.user_id, keyword_id=keyword_id)
