# Context: Algorithm Specifications

> Algorithm agent exclusive. Record any formula/weight/threshold changes in decisions/.

## Early Trend Score
```python
early_score = (0.40 * growth_rate_72h
             + 0.30 * cross_platform_score
             + 0.20 * velocity_accel
             + 0.10 * niche_signal)
# growth_rate_72h: 72h mention growth rate (normalized 0-1)
# cross_platform: simultaneous appearance on X, Reddit, Instagram, news
# velocity_accel: acceleration d²mention/dt²
# niche_signal: early reaction in expert communities
# score > 0.70 → Emerging (Pro+)
# score > 0.85 → Hot Emerging + push notification (Business+)
```

## Burst Detection Ensemble
```python
burst_score = 0.40*prophet + 0.35*iforest + 0.25*cusum
# Prophet: yhat_upper * 1.5 exceeded
# IsolationForest: contamination=0.01
# CUSUM: max(0, prev + freq - mu - k), k=mu*0.5
# MEGA: >0.90 / HIGH: >0.75 / NORMAL: >0.60 / END: <0.30
```

## ScoreCalculator
```python
freshness = 100 * exp(-lambda * t_minutes)
# lambda: breaking=0.10 / politics=0.04 / IT=0.02 / default=0.05
score = freshness + source_weight + article_count_bonus + social_signal + keyword_importance
```

## SemanticClusterer
```python
# Stage 1: Jaccard(keywords) — O(1) early filter
# Stage 2: cosine(KR-SBERT-V40K) — threshold dynamic per category
sim(A,B) = 0.50*cosine + 0.25*jaccard + 0.15*temporal + 0.10*source
```

## LambdaMART LTR (17 features)
| Group | Features |
|---|---|
| Temporal | freshness_exp · hour_of_day · age_bucket |
| Source | source_reliability · diversity_bonus |
| Engagement | group_count · social_signal · CTR · dwell_time |
| Content | body_length · has_summary · keyword_importance |
| Personalization | category_weight · source_affinity · cf_score |
| Context | fatigue_penalty · diversity_bonus (MMR λ=0.7) |

## ActionInsightEngine
```
Input: trend keyword + news Top10 + SNS Top20 + user role
Role prompts:
  marketer → 3 promotion/ad opportunity points
  creator  → content title draft + upload timing + SEO keywords
  owner    → consumer reaction summary + product development hints
  general  → SNS post draft + participation method
Anti-hallucination: source context only, no AI inference, source URL required
Cache: insights:{role}:{keyword} TTL 1h
AI model: configurable via admin_settings (default: Gemini Flash)
```

## AI Model Configuration
- AI model used by AISummarizer and ActionInsightEngine is configurable
- Admin can change model (Gemini Flash / GPT-4o-mini / etc.) in admin panel
- Fallback chain: primary → secondary → TextRank (rule-based)
- Config key: admin_settings['ai.primary_model'], admin_settings['ai.fallback_model']
