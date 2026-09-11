# Hardening Changelog — 2026-09-11

- Added database-backed login failure tracking and temporary lockout.
- Increased public registration/password-change minimum password length from 6 to 8.
- Validated profile, post, product, seller and delivery media URLs.
- Replaced the HTTP-only Nginx example with an HTTPS-ready production template.
- Added Nginx HSTS/security headers.
- Added Docker CPU/memory resource limits.
- Archived historical/conflicting markdown status files and added authoritative `STATUS.md`.
