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
