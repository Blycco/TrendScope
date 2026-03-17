# Feature: Admin Panel

Completely separate from user-facing UI (routes: /admin/*)
Access: admin + operator roles, 2FA required
See context/admin.md for full spec

Key capabilities:
- User management (view, modify plan/role, suspend, delete)
- Subscription & payment management
- Source quota management (view, change limit, reset usage)
- AI model configuration (change primary/fallback, test)
- System settings (all admin_settings with reset-to-default)
- Audit log viewer + export (JSON/CSV)
- Analytics dashboard (users, revenue, feature usage, errors)
