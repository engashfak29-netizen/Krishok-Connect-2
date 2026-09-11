# Krishok Connect — NEXT31–NEXT35 Complete

Base: NEXT30 Marketplace Tags + Targeting.

## NEXT31 — Marketplace Search
- Marketplace search now uses backend `/api/v1/marketplace/search`.
- Search matches product name, description, category and JSON tags.
- Leading `#` is normalized.
- Marketplace UI shows product tags and targeted sponsored ads.
- General Search continues to search people, products, posts and sponsored ads.

## NEXT32 — Structured Area Targeting
Added structured user location fields:
- division
- district
- upazila
- union_name
- area_name

Seller areas already contain the same hierarchy. Matching now prefers structured fields; legacy free-text `users.location` remains a backward-compatible fallback.

APIs:
- `GET /api/v1/users/me/location`
- `PUT /api/v1/users/me/location`

## NEXT33 — Delivery / Return / Payout
Added:
- order status history
- return request lifecycle
- marketplace staff return management
- seller payout records
- finance payout management
- automatic payout eligibility creation when an order reaches `delivered`

Payout fee is configurable with `MARKETPLACE_PAYOUT_FEE_PERCENT`.

## NEXT34 — bKash / Nagad Payment Layer
The existing payment system is hardened into a gateway-adapter boundary:
- order ownership validation
- idempotent payment initiation
- configurable bKash/Nagad checkout adapter endpoint
- provider headers through environment configuration
- signed webhook verification using HMAC-SHA256
- payment status updates are not trusted from public users
- Finance permission remains required for manual status changes

Environment:
- `BKASH_CHECKOUT_URL`
- `BKASH_HEADERS_JSON`
- `NAGAD_CHECKOUT_URL`
- `NAGAD_HEADERS_JSON`
- `PAYMENT_RETURN_URL`
- `PAYMENT_WEBHOOK_SECRET`

No fake paid status is generated when provider credentials are absent.

## NEXT35 — OTP / SMS Security
- 6-digit OTP
- 5-minute expiry
- maximum 5 attempts
- 60-second resend protection
- previous unused codes invalidated
- hashed OTP storage
- management login remains Password + OTP
- provider adapters use `SMS_OTP_URL` / `EMAIL_OTP_URL`
- `ALLOW_DEV_OTP=false` by default

Actual provider credentials are deployment secrets and are intentionally not embedded in source code.
