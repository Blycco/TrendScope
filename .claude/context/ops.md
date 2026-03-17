# Context: Operations — CI/CD · A/B Testing

> Infra · Backend agents reference this.

## CI/CD Pipeline
```
CI (on PR):
  - pytest ≥70% coverage
  - ruff check + ruff format --check
  - mypy --ignore-missing-imports
  - SvelteKit build
  - Docker image build (Linux)
  - Security scan (no secrets in diff)

CD (on merge to main, after Jiny approval):
  - Trigger blue-green deploy (see context/infra.md)
  - Post-deploy smoke test
  - Notify on success/failure
```

## A/B Testing
```python
# Bucket assignment
bucket = mmh3.hash(f'{user_id}:{experiment_id}') % 100

# Primary metrics
CTR@5 · dwell_time · scrap_rate

# Guardrail metrics
skip_rate · dislike_rate · API p95
```

## Admin-configurable Settings (via admin panel)
All of the following are stored in admin_settings table and editable from admin panel with reset-to-default:
- AI primary model + fallback model
- Plan limits (quota values per plan)
- Source quotas (per-source quota_limit)
- Rate limiting thresholds
- Feature flags (enable/disable features)
- Notification templates
- Crawler schedules
