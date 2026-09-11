# NEXT8 Security & Payment Hardening

- Payment status can no longer be marked paid by a normal buyer.
- A signed `/api/v1/payments/webhook` endpoint is available for the real bKash/Nagad adapter.
- Checkout uses an immediate SQLite transaction and conditional stock decrement to reduce overselling.
- Security response headers are enabled.
- Checkout validates supported payment methods.

Before production, set a strong `SECRET_KEY`, `PAYMENT_WEBHOOK_SECRET`, restrictive `CORS_ORIGINS`, and real payment gateway credentials. HTTPS and a production WSGI/ASGI deployment are required.
