> **Current launch decision:** Payment gateway and OTP functionality are intentionally removed from the active build and deferred to a later phase.

# Krishok Connect — Initial Launch Completion

## Locked initial-launch policy
- OTP frontend/backend remains implemented but hidden/disabled by default (`REQUIRE_ACCOUNT_VERIFICATION=false`).
- Real online payment gateway remains implemented as a future integration boundary and is not active.
- Seller payment-account information remains available on Seller Page for buyer/seller direct arrangements and COD.
- Seller subscription is free by default (`SELLER_SUBSCRIPTION_FREE=true`) during the engagement phase; Admin can manually manage subscription status.

## Completed hardening in this pass
- Public registration now creates an immediately usable account when verification is disabled, while preserving the OTP path for later enablement.
- Login blocks unverified accounts only when `REQUIRE_ACCOUNT_VERIFICATION=true`.
- Seller subscription purchase flow no longer asks for payment in free-launch mode; it activates the selected plan directly for its duration.
- Chat list now uses backend conversations rather than the local `KC.chats` cache.
- Conversation message endpoint supports bounded pagination (`limit`, `before`) to avoid unbounded message payloads.
- Existing private farm/journal, crop intelligence, marketplace, seller payment-account, RBAC, AI, notifications, and WebRTC foundations are preserved.

## Validation
- Python compile: PASS
- All JavaScript syntax checks: PASS (34 files)
- Existing static audit: PASS
- Project file count: 137

## Still environment/provider dependent
These are intentionally not activated for the initial launch and cannot be certified without real infrastructure/provider credentials:
- Real bKash/Nagad/Rocket gateway transactions
- SMS/email OTP delivery
- FCM/APNs production push credentials
- Production TURN servers
- Production PostgreSQL deployment
- Object storage/CDN
- Domain/HTTPS and production secrets
- Real-device/load/stress testing

These are deployment/integration activities, not reasons to enable payment or OTP in the initial UI.
