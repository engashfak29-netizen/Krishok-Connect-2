# Crop Intelligence Backend

NEXT22 defines the backend data model for Krishok Connect's crop intelligence system.

## Layers
1. Category -> Crop -> Variety
2. Lifecycle stage (day range + phenological stage)
3. Region + season
4. Management rules: fertilizer, irrigation, weed, soil, IPM and general operations
5. Pest and disease records
6. Problem actions: prevention, early response, emergency response
7. Treatment records with active ingredient, formulation, registered crop, dose, method, PHI and safety
8. Crop media/image references
9. Notification rules
10. Farmer crop profiles and notification delivery log

## Safety
Treatment records are status-gated. Only `approved` treatment/rule data is returned to farmer-facing intelligence endpoints. AI must not invent pesticide dose; missing verified data is surfaced as missing data.

## Main endpoints
- `GET /api/v1/crops/catalog`
- `GET /api/v1/crops/{crop_id}/intelligence`
- `GET /api/v1/crops/{crop_id}/schedule?age_day=...`
- `GET /api/v1/crops/{crop_id}/notifications?age_day=...`
- `POST /api/v1/ai/diagnose` with `crop`, optional `age_day`, `region_id`, `season`, and image
- `POST /api/v1/farmer/crops`
- `GET /api/v1/farmer/crops`
- Admin CRUD under `/api/v1/admin/crop-intelligence/*`
- `POST /api/v1/admin/crop-intelligence/notifications/generate`

The design is additive and does not remove the existing AI ingestion or diagnosis tables.
