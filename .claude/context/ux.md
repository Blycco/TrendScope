# Context: UX & Error Handling

> Frontend agent exclusive reference.

## UX Priority
- UX always wins over UI in any conflict
- No emojis in UI — use lucide-svelte icons or equivalent
- Use shadcn/ui as base component library
- Reference existing design patterns and external references before building new UI

## Error Modal Standard
All user-facing errors MUST be shown as modal alerts. Never show raw error messages.

Modal structure:
```
Title:        User-friendly title (i18n key)
Message:      Plain-language explanation (i18n key)
Error Code:   Developer-readable code (e.g. ERR_QUOTA_EXCEEDED)
Action:       Primary CTA (e.g. "Upgrade Plan", "Try Again", "Contact Support")
```

Error code examples:
```
ERR_QUOTA_EXCEEDED      — daily/monthly limit reached
ERR_PLAN_REQUIRED       — feature requires higher plan
ERR_AUTH_REQUIRED       — not logged in
ERR_2FA_REQUIRED        — 2FA verification needed
ERR_INVALID_CREDENTIALS — login failed
ERR_SESSION_EXPIRED     — token expired
ERR_SERVER              — unexpected server error (show support link)
ERR_SOURCE_UNAVAILABLE  — data source temporarily down
```

## Quota Exceeded Modal
```
Title: "사용량 한도 초과" (i18n: modal.quota_exceeded.title)
Message: "오늘의 {feature} 사용 한도({limit}회)에 도달했습니다.
          한도는 {reset_time}에 초기화됩니다."
Error Code: ERR_QUOTA_EXCEEDED
CTA: "플랜 업그레이드" → /pricing
```

## Form Validation
- Inline validation on blur
- Submit-level validation with error summary
- All messages use i18n keys
