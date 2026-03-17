# Phase 2 / Backend Tasks (Weeks 3-4)
> Agent: Backend | Parallel with Algorithm

- [ ] backend/crawler/sources/rss_feeds.py — source URL constants (domestic 120+ / global 70+)
- [ ] backend/crawler/sources/news_crawler.py — ETag + If-Modified-Since
- [ ] backend/crawler/sources/extractor.py — 3-stage body extraction fallback
- [ ] backend/crawler/sources/robots.py — robots.txt compliance
- [ ] backend/crawler/sources/sns_crawler.py — Reddit JSON + Nitter RSS + YouTube API
- [ ] backend/crawler/sources/community_crawler.py — DC, FM Korea RSS+crawl
- [ ] backend/crawler/quota_guard.py — check/increment source quota before each call
- [ ] backend/crawler/scheduler.py — APScheduler (news 5min / SNS 2min / quota reset daily)
- [ ] backend/processor/pipeline.py — orchestrator

Done: scheduler running · articles saved to DB · quota tracking verified
