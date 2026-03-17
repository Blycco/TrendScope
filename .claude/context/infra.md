# Context: Infrastructure & Deployment

> Infra agent exclusive.

## Environments
- **Local development**: Docker Compose on developer machine
- **Production**: Ubuntu Linux cloud server, Docker-based, Linux images

## Blue-Green Deployment (zero downtime mandatory)
```
Pre-deploy:
  1. DB backup (pg_dump)
  2. alembic upgrade head (run against green DB if schema change)

Deploy:
  1. Pull new image to green container
  2. Start green container (docker compose up -d --no-deps api-green)
  3. Health check green: GET /health → 200 (max 60s)
  4. Switch Nginx upstream from blue to green
  5. Verify traffic routing
  6. Stop blue container

Rollback (automatic on healthcheck failure):
  1. Keep blue running
  2. Revert Nginx upstream to blue
  3. Stop green
  4. Alert via monitoring

Requirement: at no point should all API containers be down simultaneously.
```

## Docker Compose Services
```yaml
services:
  api-blue / api-green   — FastAPI (active + standby)
  processor              — Algorithm pipeline
  crawler                — News/SNS crawlers
  frontend               — SvelteKit SSR
  nginx                  — Reverse proxy + SSL
  postgres               — PostgreSQL 15
  redis                  — Redis 7
  prometheus             — Metrics collection
  grafana                — Metrics visualization
```

## Environment Variables (never hardcoded)
All secrets and config via .env files (never committed):
- DATABASE_URL, REDIS_URL
- JWT_PRIVATE_KEY, JWT_PUBLIC_KEY
- OAUTH_GOOGLE_CLIENT_ID/SECRET, OAUTH_KAKAO_CLIENT_ID/SECRET
- PAYMENT_WEBHOOK_SECRET, PAYMENT_API_KEY
- AI_GEMINI_API_KEY, AI_OPENAI_API_KEY
- ALLOWED_ORIGINS, BASE_URL

## Health Check
- GET /health returns 200 with DB + Redis status
- Used by blue-green switch gate
