> **Current launch decision:** Payment gateway and OTP functionality are intentionally removed from the active build and deferred to a later phase.

# Krishok Connect — Final Production Completion Pack

## Locked marketplace payment model
System A / Direct Merchant Payment is the production architecture.
- Sellers pay Krishok Connect subscription fees.
- Krishok Connect takes no sales commission in the current model.
- Customer sale money is not collected into a Krishok Connect central settlement account.
- Each seller can maintain verified bKash, Nagad, Rocket or Bank payment accounts.
- Seller order-payment groups route to the selected seller's verified account.
- The database keeps seller, order, payment account and seller-order-payment entities separate so a future commission/central-settlement model can be added without rebuilding the marketplace.

## Completed in this pack
- Seller-owned payment account management API + UI.
- Verified/default payment-account states.
- Seller-order payment grouping for multi-seller orders.
- Farmer public-profile privacy: email/phone are no longer exposed by public serializers.
- Public registration now requires OTP verification before login/session issuance.
- Farm AI context builder with farm/plot/crop/activity/input/journal history.
- Farm event/context persistence foundations.
- Inventory ledger foundations and inventory adjustment endpoint.
- Delivery tracking foundations and seller/admin tracking endpoint.
- Existing RBAC, crop intelligence, AI diagnosis, knowledge ingestion, marketplace, notifications, chat and WebRTC signaling preserved.

## External production configuration still required
These are environment/provider credentials, not code features:
- Official bKash/Nagad production merchant/API credentials and provider-specific callback/webhook settings.
- Real SMS/email OTP provider.
- Real push provider (FCM/APNs or an equivalent server provider).
- Production TURN/STUN infrastructure for reliable WebRTC.
- PostgreSQL production database and migration execution.
- Object storage/CDN for production media.
- HTTPS domain and reverse proxy.
- Monitoring, backups and restore drills.

The source code deliberately does not fake successful external payments, OTP delivery, push delivery or TURN connectivity when provider credentials are absent.

## Production rules
- Set a strong random SECRET_KEY.
- Set ENABLE_API_DOCS=false in production unless temporary diagnostics are explicitly needed.
- Set exact CORS_ORIGINS; do not use `*` with authenticated production applications.
- Set ALLOW_DEV_OTP=false and ALLOW_DEV_RESET=false.
- Keep provider secrets outside source control.
- Run the migration runner before serving traffic.
- Use PostgreSQL for production and test backup/restore.
