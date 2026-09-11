# Krishok Connect — NEXT26 Staff Panels

NEXT26 completes the operational panels for every management department while preserving the NEXT25 RBAC/OTP architecture.

## Management panels
- Super Admin: retained full staff account, role, permission, enable/disable and password-reset control center.
- Admin: user management, verification, reports, analytics and audit logs.
- Crop Intelligence Staff: catalog summary, structured data entry, review/approval and catalog browser for crop intelligence records.
- AI Content Staff: knowledge file import/review/approval/retry/delete and AI diagnosis case creation/deletion.
- Marketplace Staff: product moderation, order workflow and market-price entry/listing.
- Finance Staff: finance summary, payment ledger/status management and analytics.
- Support Staff: user search, support reports and user notification tool.
- Moderation Staff: report handling, post removal and product enable/disable moderation.

## Security
- Every management login remains Password + OTP.
- Frontend role routing remains separate by department URL.
- Backend endpoints use RBAC permissions; frontend hiding is not the security boundary.
- Existing Super Admin controls were not removed.
- Crop records support draft/review/approved/rejected status. Only approved crop intelligence is consumed by the farmer-facing intelligence layer.

## Validation
- `python -m py_compile backend/app/main.py` passed.
- `node --check staff-dashboard.js` passed.
- `node --check super-admin-dashboard.js` passed.
- ZIP integrity checked with Python `zipfile.testzip()`.

## Important environment note
A full live backend import may still require the project's installed dependencies (`passlib`, `psycopg` when PostgreSQL is selected). This iteration does not claim that external payment, SMS, OTP or OpenAI provider credentials are configured.
