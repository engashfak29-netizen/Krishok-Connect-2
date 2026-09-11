# Krishok Connect — NEXT9 to NEXT13 completion notes

## NEXT9 — Payments
- Added provider adapter boundary for bKash/Nagad through `BKASH_CHECKOUT_URL` and `NAGAD_CHECKOUT_URL`.
- Order checkout creates a transaction and returns gateway metadata when configured.
- Existing signed webhook remains available.
- Real merchant credentials are intentionally not stored in source control.
- Provider-specific API contracts must be configured against the merchant account/sandbox supplied by the provider.

## NEXT10 — Reviews, reports, notifications
- Product reviews already enforce delivered-order ownership and update aggregate rating.
- Report API/admin moderation already exists.
- Notifications are persisted and can be marked individually/all read.
- Payment/order flows now produce persisted notifications.

## NEXT11 — PostgreSQL
- Backend now supports PostgreSQL `DATABASE_URL` through psycopg while retaining SQLite for local development.
- Existing SQL uses a small placeholder adapter (`?` -> `%s`) for PostgreSQL.
- `init()` schema is compatible with PostgreSQL; extra production tables are created at startup.
- Use a managed PostgreSQL database for production and run backups before migration.

## NEXT12 — Authentication/security
- Added OTP request/verify endpoints with 5-minute expiry and 5-attempt limit.
- Added password reset request/confirmation with hashed, expiring one-time tokens.
- Reset revokes active sessions.
- OTP/reset delivery uses configurable provider endpoints; development responses are disabled by default.

## NEXT13 — AI + RAG
- Added admin-managed agriculture knowledge documents/chunks.
- AI retrieves keyword-matched trusted chunks and injects them into the Ollama prompt.
- Existing safe Bengali agriculture system prompt and fallback remain.

## Important production boundary
This release completes the application-side architecture for NEXT9–13. It does **not** invent payment credentials, SMS/email provider credentials, or a third-party provider's private API contract. Those must be supplied/configured by the operator.
