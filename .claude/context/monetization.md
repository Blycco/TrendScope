# Context: Monetization & Plan Gates

> Backend agent reference for plan gate implementation.

## Plan Definitions
| Plan | Price | Trend Feed | Insights | Early Trend | Ideas | Brand Monitor | API |
|---|---|---|---|---|---|---|---|
| free | ₩0 | 10/day | 3/day | ❌ | ❌ | ❌ | ❌ |
| pro | ₩30,000/mo | unlimited | unlimited | Emerging | 5/day | ❌ | ❌ |
| business | ₩90,000/mo | unlimited | unlimited+team | Hot Emerging+alert | unlimited | 3 | 1,000/mo |
| enterprise | negotiated | unlimited | unlimited | custom | unlimited | unlimited | unlimited |

## Additional Limits
- Scraps: Free 50 / Pro+ unlimited
- Notifications: Pro 5 keywords / Business unlimited
- Reports: Pro CSV / Business CSV+PDF
- Slack+Webhook: Enterprise

## Implementation Rules
- Plan gate validation MUST be in server-side middleware — never trust client
- Quota exceeded → return structured error with error_code, message_key, upgrade_url
- Plan expiry → auto-downgrade to free (daily batch job)
- BYOK: users can input their own Gemini/OpenAI API key to reduce server costs

## Subscription Flow
1. User selects plan → POST /api/v1/subscriptions/checkout
2. Redirect to payment provider (Toss Payments / Stripe)
3. Provider webhook → POST /api/v1/webhooks/payment
4. Webhook validated (signature check) → update subscription table
5. Audit log entry created
6. User notified (email)

## Identity Verification
- Real-name verification required before subscription upgrade (Korean regulations)
- Integration: Nice / PASS or equivalent
- Stored: verification status only, NOT raw identity data

## Quota Exceeded UX
- Show modal with: current plan limits, usage, reset time, upgrade CTA
- Error code included for support reference
- i18n keys: error.quota_exceeded, error.plan_upgrade_required
