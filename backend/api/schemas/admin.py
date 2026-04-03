"""Pydantic schemas for admin endpoints. (RULE 07: type hints required)"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# --- Users ---
class AdminUserItem(BaseModel):
    id: str
    email: str
    display_name: str | None = None
    role: str
    plan: str
    locale: str
    is_active: bool
    created_at: datetime | None = None


class AdminUserListResponse(BaseModel):
    users: list[AdminUserItem]
    total: int
    page: int
    page_size: int


class AdminUserUpdateRequest(BaseModel):
    plan: str | None = None
    is_active: bool | None = None
    role: str | None = None


# --- Subscriptions ---
class AdminSubscriptionItem(BaseModel):
    id: str
    user_id: str
    plan: str
    status: str
    provider: str | None = None
    provider_sub_id: str | None = None
    started_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None


class AdminSubscriptionListResponse(BaseModel):
    subscriptions: list[AdminSubscriptionItem]
    total: int
    page: int
    page_size: int


class AdminRefundRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class AdminRefundResponse(BaseModel):
    subscription_id: str
    status: str
    refund_reason: str


# --- Sources ---
class AdminSourceItem(BaseModel):
    id: str
    source_name: str
    quota_limit: int
    quota_used: int
    is_active: bool | None = None
    updated_at: datetime | None = None


class AdminSourceListResponse(BaseModel):
    sources: list[AdminSourceItem]


class AdminSourceUpdateRequest(BaseModel):
    quota_limit: int | None = None
    is_active: bool | None = None


# --- AI Config ---
class AdminAIConfigResponse(BaseModel):
    primary_model: str | None = None
    fallback_model: str | None = None
    api_key_set: bool = False
    settings: dict = Field(default_factory=dict)


class AdminAIConfigUpdateRequest(BaseModel):
    primary_model: str | None = None
    fallback_model: str | None = None


class AdminAIConfigTestResponse(BaseModel):
    success: bool
    response_time_ms: float | None = None
    error: str | None = None


# --- Settings ---
class AdminSettingItem(BaseModel):
    key: str
    value: object
    default_value: object | None = None
    updated_at: datetime | None = None


class AdminSettingsResponse(BaseModel):
    settings: list[AdminSettingItem]


class AdminSettingsUpdateRequest(BaseModel):
    settings: dict[str, object]


# --- Audit ---
class AdminAuditItem(BaseModel):
    id: str | None = None
    user_id: str | None = None
    action: str
    target_type: str | None = None
    target_id: str | None = None
    ip_address: str | None = None
    detail: dict | None = None
    created_at: datetime | None = None


class AdminAuditListResponse(BaseModel):
    logs: list[AdminAuditItem]
    total: int
    page: int
    page_size: int


# --- Quota Alerts ---
class QuotaAlertItem(BaseModel):
    id: str
    service_name: str
    error_type: str
    status_code: int | None = None
    detail: str | None = None
    endpoint_url: str | None = None
    is_dismissed: bool
    dismissed_by: str | None = None
    dismissed_at: datetime | None = None
    email_sent: bool
    created_at: datetime | None = None


class QuotaAlertListResponse(BaseModel):
    alerts: list[QuotaAlertItem]
    total: int
    page: int
    page_size: int


class QuotaAlertCountResponse(BaseModel):
    active_count: int


# --- Analytics ---
class AdminAnalyticsResponse(BaseModel):
    metric: str
    data: dict


# --- Feed Sources ---
class FeedSourceItem(BaseModel):
    id: str
    source_config_id: str | None = None
    source_type: str
    name: str
    url: str
    category: str
    locale: str
    is_active: bool
    priority: int = 0
    config: dict = Field(default_factory=dict)
    health_status: str = "unknown"
    last_crawled_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None
    consecutive_failures: int = 0
    avg_latency_ms: float | None = None
    total_crawl_count: int = 0
    total_error_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FeedSourceListResponse(BaseModel):
    feeds: list[FeedSourceItem]
    total: int
    page: int
    page_size: int


class FeedSourceCreateRequest(BaseModel):
    source_type: str = Field(..., pattern=r"^(rss|reddit|nitter|community|google_trends)$")
    name: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., min_length=1)
    category: str = "general"
    locale: str = Field("ko", pattern=r"^[a-z]{2}$")
    source_config_id: str | None = None
    is_active: bool = True
    priority: int = 0
    config: dict = Field(default_factory=dict)


class FeedSourceUpdateRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    category: str | None = None
    locale: str | None = None
    source_config_id: str | None = None
    is_active: bool | None = None
    priority: int | None = None
    config: dict | None = None


class FeedSourceBulkToggleRequest(BaseModel):
    feed_ids: list[str] = Field(..., min_length=1)
    is_active: bool


class FeedHealthSummaryItem(BaseModel):
    source_type: str
    total: int
    healthy: int
    degraded: int
    error: int
    unknown: int


class FeedHealthDashboardResponse(BaseModel):
    summary: list[FeedHealthSummaryItem]
    last_updated: datetime


# --- Burst Jobs ---
class BurstJobItem(BaseModel):
    id: int
    triggered_at: str | None = None
    trigger_source: str
    group_id: str | None = None
    keywords: list[str]
    threshold: float
    early_trend_score: float
    articles_found: int
    duration_ms: float | None = None
    status: str
    error_detail: str | None = None
    completed_at: str | None = None


class BurstJobListResponse(BaseModel):
    items: list[BurstJobItem]
    total: int
    page: int
    page_size: int


class BurstTriggerRequest(BaseModel):
    keywords: list[str] = Field(..., min_length=1, max_length=3)
    locale: str = Field("ko", pattern=r"^[a-z]{2}$")
