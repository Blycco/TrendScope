# Context: Security & Audit

> Security agent exclusive. Backend agent references for implementation.

## Authentication
```
OAuth 2.0:    Google, Kakao
Email:        bcrypt rounds=12, email verification required on registration
Password:     min 8 chars, complexity enforced
2FA (TOTP):   required for admin roles, optional for regular users
              TOTP secret stored encrypted (AES-256)
Session:      JWT RS256
              access token: 15min
              refresh token: rotation, 30 days, stored in httpOnly cookie
Forgot PW:    time-limited token (1h), single-use, sent to verified email
```

## Authorization
```
Roles: admin | operator | user
- admin: full access including admin panel, requires 2FA
- operator: admin panel read + limited write, requires 2FA
- user: standard API access per plan
Admin routes (/admin/v1/*) require:
  1. JWT with role=admin or role=operator
  2. Active 2FA session verified within last 30min
```

## Secrets Management
```
NEVER commit secrets to git — zero tolerance policy
NEVER hardcode API keys, passwords, tokens
Use environment variables for ALL secrets
.env files are gitignored
Rotate keys if accidentally exposed: immediate incident required
```

## Audit Log
All sensitive operations must write to audit_log table (append-only):
```
User events:   login, logout, failed_login, password_change, 2fa_enable, 2fa_disable
Account:       role_change, plan_change, account_delete, data_export
Admin actions: any admin panel action (settings change, user modification, etc.)
Payment:       subscription_create, subscription_cancel, payment_fail, webhook_received
API:           quota_reset (admin), source_config_change, ai_model_change
```

Audit log export:
- Admin can export audit_log as JSON/CSV from admin panel
- Retention: minimum 1 year
- Fields: timestamp, user_id, action, resource, ip, user_agent, result, detail (JSONB)

## Network Security
- SSRF: block all internal IPs (10.x, 172.x, 192.168.x, 127.x)
- CORS: ALLOWED_ORIGINS env only
- Rate limiting: per-IP + per-user
- SQL injection: asyncpg parameterized queries only
- XSS: CSP headers via Nginx
- Payment webhooks: signature verification mandatory before processing

## Data Privacy
- Store verification status only, never raw PII from identity verification
- User data deletion: cascading delete on account_delete
- PII in logs: redact before writing (mask email, phone)
