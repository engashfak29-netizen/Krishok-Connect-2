> **Current launch decision:** Payment gateway and OTP functionality are intentionally removed from the active build and deferred to a later phase.

# Krishok Connect — Final Production Hardening Status

Build: `RBAC-STRICT-FINAL(2)` hardened build
Date: 2026-09-10

## Completed in source

- Backend route/schema static audit passes.
- Python AST/compile checks pass.
- JavaScript syntax checks pass.
- Strict RBAC/deparment isolation retained.
- Farmer Farm → Plot → Crop → Journal architecture retained.
- Seller-owned direct merchant payment architecture retained.
- Multi-seller orders now create seller-level payment splits using verified/default seller payment accounts.
- Payment webhook supports both aggregate transactions and seller-level payment transactions, duplicate-event protection, signature verification, and optional amount verification.
- Public registration OTP flow now sends an OTP when account verification is enabled and the frontend has a verification/resend flow.
- Social posts now support native video attachments with a database migration.
- Image/product/post uploads now use the authenticated media upload API instead of embedding image Data URLs in JSON.
- Marketplace location change UI is functional and persists division/district/upazila/union/area data.
- Production CORS wildcard is rejected when `ENVIRONMENT=production`.
- Production startup rejects weak/default `SECRET_KEY`.
- API docs are disabled in the production environment example.
- Media upload supports image/video/audio types with configurable size limits and SHA-256 registration.
- Production service adapters use environment configuration; no provider credentials are bundled.
- Checkout already uses an explicit database transaction with rollback on failure.
- `.pyc`/`__pycache__` artifacts are removed from the final package.

## Verification performed

- `FINAL_AUDIT.py` — PASS
- `backend/FINAL_PREFLIGHT.py` — PASS
- JavaScript `node --check` — PASS for all JS files
- Python AST/compile — PASS for backend Python files
- Migration 004 SQLite syntax smoke test — PASS

## External activation still required

These cannot be honestly marked live without the operator's production accounts, credentials, domain, infrastructure, and provider contracts:

1. bKash/Nagad/Rocket official merchant/API credentials and provider-specific request/response mapping.
2. SMS OTP provider credentials/sender configuration.
3. Production PostgreSQL instance, backups, restore test, and connection pool sizing.
4. Object storage/CDN credentials if external media storage is selected.
5. Push notification provider credentials and device delivery test.
6. TURN server credentials for reliable WebRTC across restrictive NATs.
7. OpenAI production API key/model selection and budget limits.
8. Production domain/reverse proxy/TLS configuration.
9. Real Android/iPhone and low-bandwidth network E2E testing.
10. Production agricultural knowledge dataset approval/population.

The codebase is therefore **source-complete for the identified fixable audit items**, but a responsible engineering report must keep these operator/external activation items separate from code completion.

## Final hardening update — September 2026
Added distributed Redis rate limiting, S3-compatible object storage/CDN support, authenticated private-media serving, FCM/APNs adapters, continuous worker scheduling, cursor pagination, PostgreSQL backup/restore scripts, and production QA/runbook assets. Live provider credentials, domain, real-device QA, load testing and independent penetration/agricultural validation remain external certification requirements.
