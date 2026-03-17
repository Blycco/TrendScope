# Feature: Trend Feed

Plan: Free 10/day · Pro+ unlimited
Cache: feed:trends:{category}:{locale} TTL 3min, burst invalidates immediately
Personalization: filtered by user role + category_weights + locale
API: GET /api/v1/trends, GET /api/v1/news
UI Components: TrendCard (no emojis, shadcn-based), EarlyBadge
i18n: all labels, status badges use translation keys
