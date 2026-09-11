# NEXT31–35 API Summary

### Search
- `GET /api/v1/marketplace/search?q=<term>`
- `GET /api/v1/marketplace/ads?search=<term>`

### Structured location
- `GET /api/v1/users/me/location`
- `PUT /api/v1/users/me/location`

### Orders / returns
- `GET /api/v1/orders/{order_id}/timeline`
- `POST /api/v1/orders/{order_id}/return`
- `GET /api/v1/orders/{order_id}/return`
- `PATCH /api/v1/department/market/orders/{order_id}/return?status=...`

### Seller payout
- `GET /api/v1/seller/payouts`
- `GET /api/v1/department/finance/payouts`
- `PATCH /api/v1/department/finance/payouts/{payout_id}?status=...`

### Payments
- `POST /api/v1/payments/initiate`
- `GET /api/v1/payments/order/{order_id}`
- `POST /api/v1/payments/webhook`

Webhook signature contract:
`HMAC_SHA256(PAYMENT_WEBHOOK_SECRET, transaction_id + ':' + status + ':' + provider_reference)`

### OTP
- `POST /api/v1/auth/role-login`
- `POST /api/v1/auth/verify-management-otp`
- `POST /api/v1/auth/request-otp`
- `POST /api/v1/auth/verify-otp`
