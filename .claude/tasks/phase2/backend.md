# Phase 2 / Backend Tasks (Weeks 3-4)
> Agent: Backend | Parallel with Algorithm

- [x] backend/crawler/sources/rss_feeds.py — source URL constants (domestic 120+ / global 70+)
- [x] backend/crawler/sources/news_crawler.py — ETag + If-Modified-Since
- [x] backend/crawler/sources/extractor.py — 3-stage body extraction fallback
- [x] backend/crawler/sources/robots.py — robots.txt compliance
- [x] backend/crawler/sources/sns_crawler.py — Reddit JSON + Nitter RSS + YouTube API
- [x] backend/crawler/sources/community_crawler.py — DC, FM Korea RSS+crawl
- [x] backend/crawler/quota_guard.py — check/increment source quota before each call
- [x] backend/crawler/scheduler.py — APScheduler (news 5min / SNS 2min / quota reset daily)
- [x] backend/processor/pipeline.py — orchestrator

Done: scheduler running · articles saved to DB · quota tracking verified
