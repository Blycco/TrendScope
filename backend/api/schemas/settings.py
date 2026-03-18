"""Pydantic models for user settings endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class UpdateSettingsRequest(BaseModel):
    display_name: str | None = None
    role: str | None = None
    locale: str | None = None
    category_weights: dict | None = None


class SettingsResponse(BaseModel):
    id: str
    display_name: str | None
    role: str
    locale: str
    category_weights: dict
