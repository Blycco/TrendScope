# Context: Caching Strategy

> Backend · Algorithm agents — apply caching aggressively for resource efficiency.

## Cache Key Map
| Key | TTL | Invalidation Trigger |
|---|---|---|
| feed:trends:{category}:{locale} | 3min | burst detected |
| insights:{role}:{kw} | 1h | trend score change >10% |
| trend:early:{kw} | 30min | score change >10% |
| article:{id}:summary | 6h | body updated |
| brand:{uid}:{name} | 15min | new mention |
| user:{id}:profile | 1h | settings changed |
| rss_meta:{url} | permanent | 304 response renews |
| ideas:{uid}:{kw} | 1h | manual refresh |
| admin:settings | 5min | any settings change |
| source:quota:{source} | until daily reset | quota_used update |

## Stampede Prevention
- Redis SETNX lock (TTL 30s)
- On lock failure: return stale cache + background refresh

## Memory Policy
- maxmemory-policy: allkeys-lru
- Compress long AI summary values: zlib

## Principle
When in doubt, cache it. Always measure cache hit rate (target ≥70%).
