# Context: API Specification

> Backend · Frontend agents reference this.

## Endpoints

| Method | Path | Description | Auth | Plan |
|---|---|---|---|---|
| GET | /api/v1/trends | Trend feed (role/category filter) | optional | Free: 10/day |
| GET | /api/v1/trends/early | Early Trend list | required | Pro+ |
| GET | /api/v1/trends/{kw}/insights | Role-based action points | required | Pro+ |
| GET | /api/v1/news | News feed (cursor pagination) | optional | all |
| GET | /api/v1/content/ideas | Content idea generation | required | Pro+ |
| GET | /api/v1/brand/{name}/monitor | Brand monitoring | required | Business+ |
| GET/POST/DELETE | /api/v1/scraps | Saved items | required | Free: 50 |
| POST | /api/v1/auth/oauth/{provider} | OAuth login (google/kakao) | none | all |
| POST | /api/v1/auth/register | Email registration | none | all |
| POST | /api/v1/auth/login | Email login | none | all |
| POST | /api/v1/auth/logout | Logout | required | all |
| POST | /api/v1/auth/password/forgot | Password reset request | none | all |
| POST | /api/v1/auth/password/reset | Password reset confirm | none | all |
| POST | /api/v1/auth/2fa/enable | Enable 2FA | required | all |
| POST | /api/v1/auth/2fa/verify | Verify 2FA code | required | all |
| GET/PUT | /api/v1/settings | User settings | required | all |
| PUT | /api/v1/settings/role | Role change | required | all |
| POST | /api/v1/events | Behavior event batch | optional | all |
| GET | /api/v1/subscriptions/current | Current subscription | required | all |
| POST | /api/v1/subscriptions/checkout | Start checkout | required | all |
| POST | /api/v1/subscriptions/cancel | Cancel subscription | required | all |
| POST | /api/v1/webhooks/payment | Payment provider webhook | none | all |
| GET | /admin/v1/* | Admin panel APIs | required (admin+2FA) | admin |
| GET | /health | Health check | none | all |

## Plan Gates
```python
PLAN_GATES = {
    "/api/v1/trends/early":         "pro",
    "/api/v1/trends/{kw}/insights": "pro",
    "/api/v1/content/ideas":        "pro",
    "/api/v1/brand/{name}/monitor": "business",
}
PLAN_LEVEL = {"free": 0, "pro": 1, "business": 2, "enterprise": 3}
```

## Pagination
- Cursor-based: `?cursor={score}:{id}&limit=20`
- Response: `{"items": [], "next_cursor": "str|null"}`

## Quota Exceeded Response
```json
{
  "error_code": "QUOTA_EXCEEDED",
  "message_key": "error.quota_exceeded",
  "quota_type": "daily_trends",
  "limit": 10,
  "reset_at": "ISO8601",
  "upgrade_url": "/pricing"
}
```

## Rate Limiting
- Unauthenticated: 60/min
- Authenticated: 300/min
- /events: 600/min
- Exceeded: 429 + Retry-After header
