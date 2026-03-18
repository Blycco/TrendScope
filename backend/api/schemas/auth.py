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


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


class EmailVerifySendResponse(BaseModel):
    message: str = "Verification email sent"


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# ---------------------------------------------------------------------------
# 2FA (TOTP)
# ---------------------------------------------------------------------------


class Enable2FAResponse(BaseModel):
    otpauth_url: str
    secret: str


class Verify2FARequest(BaseModel):
    totp_code: str


class TwoFALoginRequest(BaseModel):
    challenge_token: str
    totp_code: str


class TwoFARequiredResponse(BaseModel):
    requires_2fa: bool = True
    challenge_token: str


# ---------------------------------------------------------------------------
# Kakao OAuth
# ---------------------------------------------------------------------------


class KakaoOAuthCallbackRequest(BaseModel):
    code: str
    redirect_uri: str
