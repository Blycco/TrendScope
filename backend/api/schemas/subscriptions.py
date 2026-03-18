"""Pydantic models for subscription endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SubscriptionResponse(BaseModel):
    id: str
    user_id: str
    plan: str
    status: str
    provider: str | None
    provider_sub_id: str | None
    started_at: datetime
    expires_at: datetime | None
    created_at: datetime


class CheckoutRequest(BaseModel):
    plan: str


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str
