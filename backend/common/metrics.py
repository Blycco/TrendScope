"""Custom Prometheus metrics for TrendScope monitoring. (Phase 10 alert threshold tuning)"""

from __future__ import annotations

from prometheus_client import Counter, Gauge

# Cache hit/miss tracking
CACHE_REQUESTS = Counter(
    "cache_requests_total",
    "Total cache requests",
    ["result"],  # hit | miss
)

# Crawler success/failure tracking
CRAWLER_REQUESTS = Counter(
    "crawler_requests_total",
    "Total crawler requests",
    ["source", "result"],  # result: success | failure
)

# AI API call tracking
AI_API_REQUESTS = Counter(
    "ai_api_requests_total",
    "Total AI API requests",
    ["provider", "result"],  # result: success | failure
)

# Payment failure tracking
PAYMENT_FAILURES = Counter(
    "payment_failures_total",
    "Total payment webhook failures",
)

# Source quota usage ratio (used / limit)
SOURCE_QUOTA_RATIO = Gauge(
    "source_quota_ratio",
    "Source quota usage ratio (used / limit)",
    ["source"],
)
