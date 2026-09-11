# Strict Staff RBAC — Krishok Connect

- Super Admin and Admin have separate interfaces.
- Department staff use a common operational shell; authorized department views are selected from a dropdown.
- Operational departments are isolated: Crop, AI Content, Marketplace, Finance, Support, Moderation.
- Department roles cannot be granted permissions belonging to another department.
- Super Admin and Admin can authorize multiple people into the same department.
- Each person retains a separate username/password.
- Same-department staff can view shared departmental work.
- Mutation ownership is enforced through `staff_work_owners`: a staff member may edit/delete only work owned by them; Admin/Super Admin can administer.
- Cross-department requests return HTTP 403.
- Admin can authorize an existing user through `/api/v1/admin/staff/role-assignments`.
- A user cannot hold multiple operational department roles simultaneously.
