# Krishok Connect — NEXT19 Production Release

## Release gates
1. Copy `production.env.example` to `.env` and replace every `REPLACE_*`/`YOUR-DOMAIN` value.
2. Use PostgreSQL in production; do not use the SQLite default.
3. Run the SQLite migration script against a backup if migrating existing data.
4. Keep `ENABLE_API_DOCS=false` in production unless temporarily required.
5. Put Nginx/Caddy/Traefik in front of port 8000 and enable HTTPS.
6. Configure real bKash/Nagad merchant credentials and provider-specific callback verification.
7. Configure a real OTP provider; keep `ALLOW_DEV_OTP=false` and `ALLOW_DEV_RESET=false`.
8. Configure object storage/CDN before large-scale media use.
9. Configure TURN for reliable WebRTC across restrictive networks.
10. Run `python smoke_test.py https://YOUR-DOMAIN.example` after deployment.

## Database
Production compose uses PostgreSQL 16. Create `.env` with `POSTGRES_PASSWORD` and matching `DATABASE_URL`.

## Backups
Run `./backup.sh` daily via cron/systemd. Keep encrypted off-server copies and periodically test restore.

## Rollback
Keep the previous image/tag. On failed release: stop the new API, restore the previous image, and only roll back the database when a tested reversible migration exists.

## Security
- Never commit `.env`, credentials, tokens or database dumps.
- Rotate `SECRET_KEY`/webhook secrets if exposed.
- Restrict database to the private network.
- Review Nginx logs and API audit logs.
- Enable HTTPS before exposing login/payment endpoints.
