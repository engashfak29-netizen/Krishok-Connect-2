# Krishok Connect — Final Connection Audit

## Fixed
- Unified frontend API client in `api.js`.
- Added backward-compatible `A()` adapter used by management pages.
- Added backward-compatible `KCAuth` adapter used by legacy admin UI.
- Fixed login/register API calls and loaded `api.js` before `auth.js`.
- Register password validation now matches backend minimum 8 characters.
- Fixed missing `api_client.js` references in admin pages.
- Fixed broken `backend/app/api_client.js` reference in AI Knowledge pages.
- Fixed local WebView/file-path management page references.
- Added the missing FastAPI `POST /api/v1/ai/chat` route decorator.
- Kept the existing APK artifact inside the project.

## Backend endpoints checked
All literal `/api/v1/...` frontend calls were compared against backend route declarations.
The only missing route found was `/api/v1/ai/chat`; its route decorator was added.

## APK/network limitation
The existing `app-debug.apk` is a compiled artifact and cannot be changed merely by editing source files.
A new APK build is required for source fixes to be packaged into the APK.

For an Android physical device, `127.0.0.1` means the device itself. The APK therefore needs a reachable backend URL in `KC_API_BASE` (or a local backend on the phone / a host-network bridge) before remote backend requests can succeed.
