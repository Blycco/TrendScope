"""Pydantic models for notification settings and keyword alert endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NotificationSettingResponse(BaseModel):
    id: str
    user_id: str
    type: str
    channel: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class NotificationSettingUpdate(BaseModel):
    type: str
    channel: str
    is_enabled: bool


class NotificationSettingsResponse(BaseModel):
    settings: list[NotificationSettingResponse]


class KeywordCreateRequest(BaseModel):
    keyword: str


class KeywordResponse(BaseModel):
    id: str
    user_id: str
    keyword: str
    created_at: datetime


class KeywordsResponse(BaseModel):
    keywords: list[KeywordResponse]
