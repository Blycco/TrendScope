# Phase 2 / Algorithm Tasks (Weeks 3-4)
> Agent: Algorithm | Parallel with Backend

- [x] backend/processor/shared/text_normalizer.py
- [x] backend/processor/shared/dedupe_filter.py — Bloom Filter + Redis SET 3-stage
- [x] backend/processor/shared/keyword_extractor.py — soynlp + TF-IDF × BM25
- [x] backend/processor/shared/score_calculator.py — freshness exponential decay
- [x] backend/processor/shared/spam_filter.py — XGBoost (cold start: rule-based)
- [x] backend/processor/algorithms/burst.py — Prophet + IForest + CUSUM
- [x] backend/processor/shared/semantic_clusterer.py — Jaccard + MiniLM-L6

Done: pipeline runs · keywords + scores saved to DB
