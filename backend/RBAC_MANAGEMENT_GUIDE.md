# Krishok Connect — Management RBAC

## Architecture
Management access is separated by department and role. Every management login uses its own URL namespace and the backend checks the assigned role/permissions on every request.

Roles: super_admin, admin, crop_admin, content_admin, market_admin, finance_admin, support_admin, moderation_admin.

## Authentication
Management login: password -> OTP -> session/JWT. Public users use the normal public login flow and are not forced through management OTP.

## Super Admin controls
- Create management staff
- Assign primary/additional roles
- Enable/disable staff accounts
- Reset staff passwords (old sessions revoked)
- Edit role permissions
- View staff roles and effective permissions

Super Admin permissions cannot be reduced by the UI/API.

## Security rules
- Disabled management staff are blocked at token validation level.
- Direct URL access does not grant access.
- API endpoints enforce permission/role server-side.
- Role and permission changes are audit logged.
- Passwords are hashed; OTP codes are stored hashed.
- Production must configure SMS_OTP_URL and/or EMAIL_OTP_URL and set ALLOW_DEV_OTP=false.
