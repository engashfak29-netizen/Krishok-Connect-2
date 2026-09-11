> **Current launch decision:** Payment gateway and OTP functionality are intentionally removed from the active build and deferred to a later phase.

# Krishok Connect — Full Production Audit Report

Audit date: 2026-09-10
Audited build: FINAL-PRODUCTION-COMPLETE

## Executive result

The codebase is structurally complete for the implemented product scope and passes static validation. It is **not yet possible to certify it as live-production-ready from this package alone**, because several production integrations require real third-party credentials/services and real-device/network testing.

## Verified in this audit

- Python AST/compile validation: PASS
- JavaScript syntax validation: PASS
- ZIP extraction/integrity: PASS
- System A seller-owned payment account schema/routes: PRESENT
- Seller payment account ownership checks: PRESENT
- Seller default/active/verification states: PRESENT
- Public profile serializer removes email/phone/password: PRESENT
- Public registration does not issue a session token before verification: PRESENT
- Farmer private farm/journal endpoints and context foundation: PRESENT
- Inventory/delivery foundation: PRESENT
- RBAC department namespaces and permission layer: PRESENT
- AI diagnosis/knowledge ingestion foundation: PRESENT
- Existing marketplace/cart/order/payment transaction foundation: PRESENT

## Production blockers / external dependencies

### P0 — must be completed before public launch
1. Configure and validate official bKash/Nagad production integration according to provider agreement.
2. Configure real SMS/OTP provider and test delivery, retry and abuse limits.
3. Deploy PostgreSQL and perform migration + restore test.
4. Deploy production object storage/CDN for media; do not rely on local media storage for scale-out.
5. Configure HTTPS/reverse proxy, production CORS and strong secrets.
6. Configure reliable WebRTC TURN infrastructure.
7. Configure production push notification infrastructure (FCM/Web Push as applicable).
8. Perform real-device E2E tests on Android and low-bandwidth networks.
9. Perform security, concurrency and load/stress tests.
10. Configure monitoring, backups, alerts and operational job scheduling.

## Important code-level hardening still recommended

- Replace remaining prototype prompt/alert flows with production modal/form UX.
- Add a normalized farm event model and make the new farm/journal model the single source of truth instead of maintaining parallel legacy crop records.
- Make multi-step journal/order/payment workflows explicit transactions where atomicity is required; current helper commits individual SQL statements.
- Complete production conversation pagination/presence/read state and WebRTC reconnect/busy/missed-call handling.
- Complete marketplace logistics edge cases: partial cancellation/return/refund, failed delivery, delivery proof and inventory ledger integration.
- Add malware scanning to uploaded media.
- Add vector/RAG retrieval, source traceability and knowledge versioning for production AI.
- Add session cleanup/rotation and stronger login abuse controls.
- Run browser-level asset-path tests for staff/static resources.

## System A payment decision

Krishok Connect uses **Direct Merchant Payment** as the current locked marketplace model:

- Sellers pay Krishok Connect subscription fees.
- Krishok Connect does not take a sales commission under the current model.
- Krishok Connect does not centrally collect seller sale proceeds.
- Each seller owns and controls their verified bKash/Nagad/Rocket/bank payment accounts.
- Future commission-based marketplace functionality can be added as a separate payment/settlement layer without redesigning the whole marketplace.

## Test limitation

The local audit environment did not have `passlib` installed, so a live FastAPI process could not be started there. The project's declared requirements include `passlib[bcrypt]==1.7.4`. The smoke test therefore reported connection refused because no API server was running. This is an environment/dependency validation limitation, not evidence that the application code itself is syntactically invalid.

## Launch certification

Status: **READY FOR FINAL INTEGRATION + STAGING QA, NOT CERTIFIED FOR PUBLIC PRODUCTION YET.**

A true production certification requires the P0 items above to be configured and tested in the target hosting environment.
