# Context: Common/Shared Code

> All agents — use shared code before writing new utilities.

## Backend Common (backend/common/)
```
backend/common/
  paths.py        — all path constants (never use string literals for paths)
  errors.py       — error code definitions + structured error responses
  pagination.py   — cursor pagination utilities
  auth.py         — JWT decode/encode helpers
  validators.py   — shared input validators
  quota.py        — quota check/increment helpers
  audit.py        — audit log write helpers
```

## Frontend Common (frontend/src/lib/)
```
frontend/src/lib/
  api/            — typed API client
  stores/         — global state (user, plan, locale)
  ui/             — shadcn-based shared components
    Modal.svelte
    ErrorModal.svelte
    QuotaExceededModal.svelte
    PlanGate.svelte
    Badge.svelte
  i18n/           — translation files
  utils/          — date, format, string helpers
```

## Principle
Before writing a new utility function: check if it exists in common/.
If a pattern is used in 2+ places: extract to common/.
