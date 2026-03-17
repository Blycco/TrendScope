# 2026-03-12 — Initial Technology Stack Decisions

## Ubuntu Linux Cloud + Docker
Reason: standard Linux environment, portable Docker images, no vendor lock-in
Tradeoff: requires manual server setup vs managed PaaS

## asyncpg over SQLAlchemy
Reason: async-native, no ORM overhead, direct query control
Tradeoff: no ORM convenience, parameterized queries must be written manually

## Gemini Flash (default, admin-configurable)
Reason: generous free quota to start; cost-efficient
Tradeoff: Korean language quality may vary; GPT-4o-mini fallback configured

## SvelteKit over Next.js
Reason: built-in SSR, smaller bundle, compile-time optimization
Tradeoff: smaller ecosystem vs React

## Blue-Green Deployment
Reason: zero downtime mandatory for subscription service
Tradeoff: requires double container resources during switch window

## shadcn/ui for Frontend
Reason: accessible, composable, unstyled base — fits UX-first approach
Tradeoff: requires more setup than opinionated UI libraries

## Admin Settings in DB (admin_settings table)
Reason: all configurable values changeable at runtime without redeploy
Tradeoff: cache invalidation needed when settings change
