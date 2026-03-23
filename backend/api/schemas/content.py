"""Pydantic schemas for content ideas API."""

from __future__ import annotations

from pydantic import BaseModel


class ContentIdeaRequest(BaseModel):
    keyword: str
    sources: list[dict] = []


class ContentIdeaItem(BaseModel):
    title: str
    hook: str
    platform: str
    difficulty: str


class ContentIdeaResponse(BaseModel):
    ideas: list[ContentIdeaItem]
    cached: bool
