# Feature: Onboarding & Authentication

Onboarding flow (mandatory on first login):
  Step 1: Role selection (marketer / creator / owner / general)
  Step 2: 3 interest categories (food · fashion · IT · beauty · leisure · finance · sports · entertainment)
  Step 3: Domestic/global ratio slider (default 70:30)
  → Personalized dashboard generated immediately

Authentication methods:
  Google OAuth 2.0
  Kakao OAuth 2.0
  Email + password (bcrypt rounds=12, email verification required)
  Anonymous session (UUID, migrate on signup)

Email auth flows:
  Register: email → verification link → set password
  Login: email + password (+ 2FA if enabled)
  Forgot password: email → time-limited reset link (1h, single-use)
  2FA: TOTP setup + backup codes

DB: user_profile.role / category_weights / locale / user_identity (multi-row per user)
UI: RoleOnboarding (shadcn, no emojis), PlanGate modal
i18n: all onboarding strings use translation keys
