# Krishok Connect — NEXT14–18

## 14 Weather + Market Prices
- Open-Meteo weather endpoint with 15-minute cache and crop-friendly advisory.
- Market price filters/trends and configurable `MARKET_PRICE_URL` JSON importer.
- Expected feed shape: `{ "prices": [{"crop":"ধান","market":"ঢাকা","price":35,"unit":"kg","date":"YYYY-MM-DD","source":"..."}] }`.

## 15 Social
- Post edit/delete/share APIs.
- User/post reporting and moderation remain protected by authentication/admin roles.

## 16 Chat / Calls
- REST + WebSocket chat remains available.
- Call signaling endpoint remains available and browser media permission UI is enabled.
- Configure TURN servers for production NAT traversal; set `window.KC_TURN_SERVERS` from deployment config.

## 17 Admin
- Analytics endpoint: users, verified users, posts, products, orders, revenue, reports, notifications and paid payments.
- Audit log endpoint for admin.

## 18 Security / Operations
- Request ID, basic per-IP API rate limiting, structured application logging, readiness endpoint, security headers, upload type/size validation and audit logging.
- Use HTTPS, reverse proxy, strong `SECRET_KEY`, strong `PAYMENT_WEBHOOK_SECRET`, restricted CORS, PostgreSQL, object storage, backups and external monitoring in production.

## Important
No provider credentials are hardcoded. Payment/SMS/market-price providers require real credentials and a provider contract before live activation.
