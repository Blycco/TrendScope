# Context: Data Collection Pipeline

> Backend · Algorithm agents reference this.

## Source Config (admin-managed)
All sources are configured via admin_settings / source_config table.
- quota_limit: max requests per day (0 = unlimited)
- quota_used: current usage (reset daily by cron job)
- enabled: boolean (admin can disable per source)
- Developer can reset quota_used and change quota_limit from admin panel

## Collection Sources

| Source | Method | Default Quota | Notes |
|---|---|---|---|
| News (domestic 120+ / global 70+) | RSS + ETag | unlimited | 304 skip for efficiency |
| X / Twitter | API v2 + Nitter RSS fallback | 1,500/month | auto-switch on limit |
| Reddit | JSON API | 60/min | effectively unlimited |
| YouTube | Data API v3 | 10,000 units/day | trending videos |
| Naver DataLab | Official API | 1,000/day | domestic search trends |
| Google Trends | RSS geo=KR | unlimited | RSS-based |
| Domestic communities | RSS + crawl | unlimited | DC, FM Korea, etc. |
| Instagram | Public hashtag feed | limited | ToS compliance required |

## Quota Management Rules
- Before each API call, check source_config.quota_used vs quota_limit
- If quota_limit > 0 and quota_used >= quota_limit → skip source, log warning
- Increment quota_used after successful call
- Daily cron resets quota_used for all sources
- Admin can manually reset quota_used and change quota_limit from admin panel
- If source is disabled, skip entirely

## News Processing Pipeline
```
RSS + ETag (304 skip)
→ DedupeFilter (Bloom Filter FP 0.1% + Redis SET 3-stage)
→ Body extraction (3-stage fallback)
→ TextNormalizer
→ SpamFilter (XGBoost)
→ KeywordExtractor (soynlp + TF-IDF × BM25)
→ SemanticClusterer (Jaccard + MiniLM-L6)
→ ScoreCalculator (freshness decay)
→ EarlyTrendScore
→ AISummarizer (ROUGE gate, configurable model)
→ ActionInsightEngine (role-based, configurable model)
→ CacheManager.warm
→ DB save
```

## SNS Pipeline
```
Collect (X · Reddit · YouTube · Naver · communities)
→ DedupeFilter → TextNormalizer → KeywordExtractor
→ trend_score = mention_count × recent_growth × engagement × burst_strength
→ Related keyword map (cosine similarity > 0.65)
→ Propagation path tracking
→ KoELECTRA sentiment analysis
→ BurstDetector → EarlyTrendScore → ActionInsightEngine
→ CacheManager.warm → DB save
```

## Scheduler
- News crawler: every 5 minutes
- SNS crawler: every 2 minutes
- EarlyTrend recalculation: every 10 minutes
- Quota used reset: daily 00:00
- Plan expiry batch: daily 01:00
- ALS recommendation batch: daily 03:00
