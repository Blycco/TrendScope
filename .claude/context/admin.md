# Context: Admin Panel

> Frontend · Backend agents reference for admin panel work.

## Access Control
- Roles with access: admin, operator
- All admin routes: /admin/v1/* (API) and /admin/* (UI)
- Requires: JWT with admin/operator role + 2FA session verified within 30min
- Admin UI completely separate from user UI (different routes, different layouts)

## Admin Panel Sections

### User Management
- List, search, filter users
- View user profile, subscription, quota usage
- Manually change plan / role
- Suspend / delete accounts
- View user audit trail

### Subscription & Payments
- View all subscriptions (active, cancelled, expired)
- View payment history and failed payments
- Manual refund trigger
- Override plan for specific users

### Content & Source Management
- Enable/disable each data source
- Change quota_limit per source
- Reset quota_used per source (manual)
- View source health and error rates

### AI Model Configuration
- Change primary AI model (Gemini Flash / GPT-4o-mini / etc.)
- Change fallback AI model
- Test model with sample input
- View AI API usage and costs

### System Settings (admin_settings table)
- All configurable settings in one place
- Each setting shows current value + default value
- Reset individual setting to default
- Reset all settings to defaults
- Settings categories:
  - Plan limits (quota per plan per feature)
  - Rate limiting thresholds
  - Crawler schedules
  - Feature flags
  - Notification templates
  - AI model selection

### Audit Log
- View all audit log entries
- Filter by user, action, date range, result
- Export as JSON or CSV

### Analytics & Insights
- Active users (DAU/MAU/WAU)
- Subscription breakdown by plan
- Feature usage statistics
- Revenue metrics (MRR, churn rate)
- Source health dashboard
- Error rate dashboard
- Trend topic analytics

## Operator vs Admin Differences
| Capability | Operator | Admin |
|---|---|---|
| View all sections | ✅ | ✅ |
| Change system settings | ❌ | ✅ |
| Change AI model | ❌ | ✅ |
| Delete users | ❌ | ✅ |
| Export audit logs | ✅ | ✅ |
| Manual plan override | ✅ | ✅ |
| Reset source quotas | ✅ | ✅ |
