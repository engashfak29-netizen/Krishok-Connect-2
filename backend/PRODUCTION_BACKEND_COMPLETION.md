# Production Backend Completion

Implemented after NEXT36-39.

## Included
- Versioned PostgreSQL/SQLite migrations in `migrations/`.
- Payment event idempotency and reconciliation ledger.
- Provider-neutral bKash/Nagad adapter via environment configuration.
- OTP provider adapter with no OTP leakage when production mode is enabled.
- Push notification outbox + provider adapter.
- Crop notification worker entry point.
- Durable media asset metadata and configurable storage backend boundary.
- Atomic inventory decrement already used by checkout; indexes added for production queries.
- Security indexes and operational job run ledger.

## External configuration required
No real provider credential is stored in source code.

Payment:
`BKASH_API_URL`, `BKASH_HEADERS_JSON`, `NAGAD_API_URL`, `NAGAD_HEADERS_JSON`, `PAYMENT_RETURN_URL`, `PAYMENT_WEBHOOK_SECRET`

OTP:
`SMS_OTP_URL`, `EMAIL_OTP_URL`, optional `OTP_PROVIDER_HEADERS_JSON`

Push:
`PUSH_API_URL`, optional `PUSH_API_HEADERS_JSON`

Storage:
`MEDIA_STORAGE_BACKEND=local|external`, `MEDIA_EXTERNAL_BASE_URL`, `MEDIA_SIGNING_SECRET`

## Worker
Use `python worker.py` every minute through cron/systemd/Kubernetes CronJob. The worker is intentionally stateless and safe to retry.
