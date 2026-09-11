# NEXT28 — Seller Page & Marketplace Sales

Implemented:
- সাধারণ User profile থেকে Seller Page খোলা
- Unique seller page slug/profile
- Seller page public profile + seller products
- Seller market area: division, district, upazila, union/area, optional radius
- Seller subscription plans: 7/30/90/180/365 days with configurable ad limits
- Subscription purchase request with payment method/reference
- Subscription remains `pending` until payment verification; no fake paid status
- Marketplace Staff can activate/reject subscription via protected API
- Active subscription required for sales ads
- Ad limits enforced per subscription
- Seller can select owned product and market area for an ad
- Seller ad CRUD

Security:
- Seller page and ads are scoped to authenticated owner
- Product/area ownership is verified server-side
- Subscription activation requires `marketplace.manage`
