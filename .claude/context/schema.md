# Context: Database Schema

> Backend · Algorithm agents reference this for all DB work.

## Core Tables (15)

| Table | Purpose | Partition |
|---|---|---|
| news_group | Deduplicated news groups + early_trend_score | none |
| news_article | Individual articles + url_hash + content_fp | publish_time monthly |
| sns_trend | SNS trend snapshots + burst_z + sentiment_badge | none |
| user_profile | Users + role + category_weights + plan + locale | none |
| user_identity | Auth methods per user (oauth, email, 2fa) | none |
| action_insight | Role+keyword action point cache | none |
| content_idea | Content idea generation results | none |
| subscription | Freemium subscriptions + payment provider | none |
| api_usage | API quota tracking per user | none |
| brand_monitor | Brand monitoring config (Business+) | none |
| scrap | Saved items + user_tags + memo | none |
| user_action_log | Behavior logs (click, scrap, dwell) | created_at monthly |
| audit_log | Security/admin audit trail (append-only) | created_at monthly |
| ab_experiment | A/B experiment definitions | none |
| source_config | API source quota config (admin-managed) | none |
| admin_settings | All admin-configurable settings with defaults | none |

## Key Columns
- news_article.url_hash = SHA-256[:16] (dedup)
- news_article.content_fp = SHA-256(title+body[:200])[:16] (content dedup)
- user_profile.role = 'marketer' | 'creator' | 'owner' | 'general'
- user_profile.locale = ISO 639-1 language code
- user_identity.provider = 'google' | 'kakao' | 'email'
- user_identity.two_fa_enabled = boolean
- subscription.plan = 'free' | 'pro' | 'business' | 'enterprise'
- audit_log.action = string (see security.md for full list)
- source_config.quota_limit = int (0 = unlimited)
- source_config.quota_used = int (reset daily)
- admin_settings.key = string, value = JSONB, default_value = JSONB

## Core Indexes
```sql
idx_ng_feed       ON news_group (category, locale, score DESC)
idx_ng_early      ON news_group (early_trend_score DESC)
idx_na_url_hash   ON news_article (url_hash)
idx_sns_early     ON sns_trend (early_trend_score DESC)
idx_sub_user      ON subscription (user_id, expires_at)
idx_ai_role_kw    ON action_insight (trend_kw, role, created_at DESC)
idx_audit_user    ON audit_log (user_id, created_at DESC)
idx_audit_action  ON audit_log (action, created_at DESC)
```
