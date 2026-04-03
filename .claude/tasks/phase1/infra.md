# Phase 1 / Infra Tasks (Weeks 1-2)
> Agent: Infra | Parallel with Backend

- [x] docker-compose.yml (all services, Linux images)
- [x] docker-compose.prod.yml (blue-green ready: api-blue + api-green)
- [x] docker-compose.test.yml
- [x] .env.example (all required env vars listed, no values)
- [x] infra/nginx/nginx.conf (reverse proxy, SSL-ready, upstream switchable)
- [x] scripts/healthcheck.sh
- [x] scripts/switch-blue-green.sh (Nginx upstream switch script)

Done: docker compose up error-free · all containers healthy
