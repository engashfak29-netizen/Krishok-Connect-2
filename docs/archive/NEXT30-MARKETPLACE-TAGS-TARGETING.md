# NEXT30 — Marketplace Tags & Area Targeting

## Product discovery
Products now support normalized search tags. Sellers can enter `#টমেটো, সবজি, দেশি_টমেটো`; the API stores clean tag values and returns them as tags.

Search matches product name, description, category and tags. A query beginning with `#` is normalized before matching.

## Sponsored ads
A seller ad can target one of the seller page's market areas. Only an `active` ad inside its schedule is eligible.

For ordinary users, `/api/v1/marketplace/ads` checks the user's saved location against the selected seller area. Management accounts receive no targeted user ads.

## Approval
Marketplace Staff can list and change ad status through:
- GET `/api/v1/department/market/ads`
- PATCH `/api/v1/department/market/ads/{ad_id}?status=active|paused|rejected|expired|draft`

An ad is not shown to users until it is `active`.

## Search
`GET /api/v1/marketplace/search?q=...` returns matching products plus matching targeted sponsored ads.
