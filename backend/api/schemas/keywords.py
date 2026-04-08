"""Pydantic response models for keyword graph endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class KeywordNode(BaseModel):
    term: str
    score: float
    frequency: int


class KeywordEdge(BaseModel):
    source: str
    target: str
    weight: float


class KeywordGraphResponse(BaseModel):
    group_id: str
    nodes: list[KeywordNode]
    edges: list[KeywordEdge]
