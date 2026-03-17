# Feature: Early Trend Detection

Plan: Free ❌ · Pro Emerging · Business Hot Emerging + push alert
Formula: early_score = 0.40*growth_72h + 0.30*cross_platform + 0.20*velocity_accel + 0.10*niche_signal
Thresholds: >0.70 Emerging · >0.85 Hot Emerging
Cache: trend:early:{kw} TTL 30min
Plan gate: Pro+ required — show ERR_PLAN_REQUIRED modal if free
API: GET /api/v1/trends/early (Pro+)
