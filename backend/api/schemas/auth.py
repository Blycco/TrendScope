"""Pydantic models for auth endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None
    locale: str = "ko"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OAuthCallbackRequest(BaseModel):
    code: str
    redirect_uri: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
    role: str
    locale: str
    plan: str
