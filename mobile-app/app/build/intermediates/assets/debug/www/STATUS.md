# Krishok Connect — Authoritative Production Status
Date: 2026-09-11
Build: kc_no_payotp_final hardened

## Launch mode
- Payment gateway: DISABLED by design.
- OTP/account verification: DISABLED by design (`REQUIRE_ACCOUNT_VERIFICATION=false`).
- Checkout: Cash on Delivery.
- Seller payment details are stored for manual settlement only; no live payment API is called.

## Security fixes included in this package
- Login and management login: persistent failed-attempt lockout (5 failures / 15 minutes by default), keyed by identifier + client IP.
- Public registration and password-change minimum password length: 8 characters.
- Profile/media URL validation rejects unsafe characters and non-HTTPS external URLs.
- Nginx production template: HTTP→HTTPS redirect, TLS 1.2/1.3, HSTS and security headers.
- Docker production resource limits added for Postgres, Redis, API and worker.
- Historical markdown documentation moved to `docs/archive/`; this file is the authoritative status.

## Still environment-dependent before public launch
1. Provision a real PostgreSQL database and Redis.
2. Set a strong production `SECRET_KEY`, database credentials and exact `CORS_ORIGINS`.
3. Provision a real domain and Let's Encrypt certificate, then replace `YOUR-DOMAIN.example` in the Nginx template.
4. Run all SQL migrations.
5. Create the first Super Admin.
6. Test backup/restore and the complete user/order/chat/notification flows.
7. Configure object storage (S3-compatible) if media must survive server replacement.
8. Add a full automated business-logic test suite.

## Important
This status file supersedes historical `NEXT*`, `FINAL_*`, and other development-status markdown files in `docs/archive/`.
