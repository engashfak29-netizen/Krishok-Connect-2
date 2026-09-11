# Krishok Connect — Production Runbook

## Required external activation
The source is prepared for PostgreSQL, Redis, S3-compatible object storage/CDN, FCM/APNs, payment gateway, SMS OTP, OpenAI and TURN. Live credentials must be supplied by the operator; none are bundled.

## PostgreSQL
1. Copy `production.env.example` to `.env` and set a strong password/secret.
2. Start: `docker compose -f docker-compose.production.yml up -d --build`.
3. Run backup daily: `./backup.sh` (host cron/systemd timer).
4. Verify restore on a separate staging database at least monthly: `./restore.sh backups/<file>.dump`.

## Redis
Set `REDIS_URL=redis://redis:6379/0` and `REQUIRE_REDIS=true` for multi-instance production. Rate limiting then becomes shared across API instances.

## Object storage
For production media set `MEDIA_STORAGE_BACKEND=s3`, `S3_BUCKET`, credentials, and optionally `S3_ENDPOINT_URL` for R2/MinIO-compatible storage. Use `MEDIA_CDN_BASE_URL` only when the CDN is intentionally public; otherwise the backend issues short-lived signed URLs.

## Push
Android: provide Firebase service-account JSON in `FCM_SERVICE_ACCOUNT_JSON`.

iOS: provide APNs `.p8` key path plus Key ID, Team ID and Bundle ID. The backend uses HTTP/2.

## Worker
The production compose runs one dedicated worker with a 60-second loop. Do not run multiple workers unless job locking/leader election is introduced.

## Domain / HTTPS
Terminate TLS at the reverse proxy using the supplied nginx example. Keep API bound to `127.0.0.1:8000`; expose only the reverse proxy.

## Payments / OTP
Provider contracts and credentials are deliberately external. Enable `REAL_PAYMENT_ENABLED` and `REQUIRE_ACCOUNT_VERIFICATION` only after sandbox/end-to-end certification.

## TURN
Set `TURN_SERVERS_JSON` to real TURN credentials before relying on calls across restrictive NATs/mobile networks.

## Production verification
Run `python FINAL_PREFLIGHT.py`, `python FINAL_AUDIT.py`, `python smoke_test.py https://YOUR-DOMAIN` and the scripts under `ops/` after deployment.
