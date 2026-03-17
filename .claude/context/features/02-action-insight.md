# Feature: Action Insights (ActionInsightEngine)

Plan: Free 3/day · Pro unlimited · Business unlimited+team share
Input: trend keyword + news Top10 + SNS Top20 + user role
Anti-hallucination: source context only, source URL required in output
AI model: admin-configurable (default Gemini Flash)
Cache: insights:{role}:{kw} TTL 1h
Quota exceeded: modal with ERR_QUOTA_EXCEEDED + upgrade CTA
API: GET /api/v1/trends/{kw}/insights (Pro+)
UI: ActionPointCard — role-based, no emojis, shadcn
