# Phase 1 / Infra Tasks (Weeks 1-2)
> Agent: Infra | Parallel with Backend

- [ ] docker-compose.yml (all services, Linux images)
- [ ] docker-compose.prod.yml (blue-green ready: api-blue + api-green)
- [ ] docker-compose.test.yml
- [ ] .env.example (all required env vars listed, no values)
- [ ] infra/nginx/nginx.conf (reverse proxy, SSL-ready, upstream switchable)
- [ ] scripts/healthcheck.sh
- [ ] scripts/switch-blue-green.sh (Nginx upstream switch script)

Done: docker compose up error-free · all containers healthy
