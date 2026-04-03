# Errors — Known Issues & Solutions

## asyncpg parameter format
Symptom: ValueError: got multiple values
Cause: asyncpg uses $1,$2 format, not %s
Fix: rewrite all queries with $1,$2 positional parameters

## Redis connection pool exhaustion
Symptom: ConnectionError: Too many connections
Fix: create pool once at startup, reuse across requests

## SvelteKit SSR env variable not exposed
Symptom: env variable undefined on client
Fix: public vars use $env/static/public or PUBLIC_ prefix

## AI model quota exceeded
Symptom: 429 ResourceExhausted from Gemini/OpenAI
Fix: check AISummarizer fallback chain is configured correctly, check admin_settings for fallback model

## Docker image not found on Linux
Symptom: no matching manifest for linux/amd64 or arm64
Fix: ensure image uses linux base, specify platform in docker-compose if needed

## Blue-green Nginx switch race condition
Symptom: brief 502 during switch
Fix: use upstream health_check before switch, keep blue running until green confirmed healthy

## Cache zlib decompression missing (PR #81)
Symptom: cached responses return raw compressed bytes instead of decoded data
Cause: Redis cache values were zlib-compressed but retrieval path skipped decompression
Fix: add zlib.decompress() on cache read path

## Admin sources $effect infinite loop (PR #80)
Symptom: browser tab freezes on Admin sources page, infinite re-renders
Cause: SvelteKit $effect reactive block triggering itself by mutating its own dependency
Fix: break the reactivity cycle by separating read/write state

## Insights UUID→keyword mismatch (PR #69)
Symptom: insight detail page shows wrong or empty data
Cause: API was looking up insights by UUID but frontend sent keyword-based identifier
Fix: align API lookup to accept keyword parameter, add proper mapping

## early_trend_score always 0 (PR #71)
Symptom: all trends show early_trend_score = 0 regardless of actual signals
Cause: score calculation formula had a missing weight multiplication
Fix: correct the score_calculator weighting logic
