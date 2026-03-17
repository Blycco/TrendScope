# Feature: Brand Monitoring

Plan: Business 3 brands · Enterprise unlimited
Detection: KoELECTRA sentiment + Z-score alert (threshold admin-configurable)
Alert latency: < 5min
Notification: email always + Slack webhook (if configured)
Cache: brand:{uid}:{name} TTL 15min
API: GET /api/v1/brand/{name}/monitor (Business+)
DB: brand_monitor (user_id · brand_name · keywords[] · alert_threshold · slack_webhook)
