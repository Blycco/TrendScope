# Context: Monitoring & Graceful Degradation

> Infra agent reference.

## Alert Thresholds & Auto-responses
| Metric | Threshold | Auto Action |
|---|---|---|
| Memory usage | > 80% | Increase crawler interval + shorten TTL |
| Cache hit rate | < 70% | Review warming strategy + Slack alert |
| Crawler failure rate | > 5% | Switch to fallback source + Slack alert |
| AI API success rate | < 80% | Auto-switch to fallback model |
| Action insight failure | 3 consecutive | Switch to TextRank rule-based |
| API p95 latency | > 500ms | Check cache hit rate |
| Payment failure | 3 consecutive | Downgrade to free + email + Slack |
| Source quota usage | > 90% | Alert admin + slow down requests |

## Graceful Degradation Chain
```
Gemini Flash fail → configured fallback model → TextRank rule-based
X API limit       → Nitter RSS fallback
Real-time ranking → stale cache (max 1h)
DB slow query     → read from cache if available
```

## Stack
- Prometheus + Grafana (metrics)
- structlog (structured logging)
- Slack Webhook (alerts)
- Audit log (security events, see context/security.md)
