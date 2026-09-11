# Krishok Connect — Final Completion Matrix

## Code-side completion in this build
- PostgreSQL production compose + migration helper + backup/restore scripts
- Redis distributed rate limiting + production Redis service
- S3-compatible object storage + optional CDN + signed URLs
- Authenticated/private media serving with public-reference exception
- FCM HTTP v1 Android push adapter
- APNs HTTP/2 iOS push adapter
- Dedicated production worker with continuous scheduler loop
- Cursor pagination endpoints for products and notifications
- Production runbook and deployment configuration
- Load/security smoke-test utilities

## Requires operator-owned external infrastructure/credentials
- Live PostgreSQL host (or the included production container stack)
- Domain/DNS/HTTPS certificate
- bKash/Nagad/Rocket/bank production merchant contracts and credentials
- SMS OTP provider/sender credentials
- FCM service account and APNs signing key
- TURN service credentials
- OpenAI API key and billing budget
- S3/R2/MinIO bucket and CDN

## Cannot be truthfully certified from source code alone
- Real Android/iPhone device certification
- 2G/3G/packet-loss/network interruption certification
- 100/500/1000 concurrent-user production benchmark
- Independent penetration test
- Agricultural expert/data validation
- End-to-end payment provider certification
- End-to-end SMS delivery certification

These are operational certification steps, not missing source-code features. The package includes scripts/runbooks to execute them after deployment.
