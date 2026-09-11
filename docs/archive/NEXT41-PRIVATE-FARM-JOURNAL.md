# NEXT41 — Private Farmer Farm Profile & AI Journal

## Locked UX
- Farmer Dashboard has one main private message box titled: **আজকে জমিতে কি কি করলেন এখানে বলুন**
- The box is intentionally empty; no placeholder/example text.
- Farmer may type or send a voice transcript.
- The farmer should not repeatedly enter static farm information.

## Backend model
- `farmer_farms`: farmer-level baseline farm profile.
- `farm_plots`: persistent plots; area is normalized to decimal while original value/unit is preserved.
- `plot_crops`: cultivation instances per plot; each planting is a historical instance.
- `farm_activity_records`: planting, irrigation, harvest, problem reports, etc.
- `farm_input_records`: fertilizer/pesticide/fungicide/other inputs with quantities when supplied.
- `farm_area_history`: immutable area/add/remove/close history.
- `farm_journal_entries`: original farmer language, parsed JSON, status and confirmation flag.

## Journal API
- `GET /api/v1/farmer/farm`
- `POST /api/v1/farmer/farm`
- `POST /api/v1/farmer/farm/plots`
- `GET /api/v1/farmer/farm/journal`
- `POST /api/v1/farmer/farm/journal`
- `POST /api/v1/farmer/farm/journal/{journal_id}/reprocess`
- `GET /api/v1/farmer/farm/activities`
- `GET /api/v1/farmer/farm/inputs`
- `GET /api/v1/farmer/ai-context`

## Natural-language changes
Example:
`১০ কাঠার উচু জমি টা বর্গা ছেড়ে দিয়ে ১ বিঘা ধানের জমি বর্গা নিলাম।`

The backend can close the matched old plot, create a new active plot, and record both operations in `farm_area_history`. It never deletes the old plot; historical cultivation data remains available.

## AI parsing
- If `OPENAI_API_KEY` is configured, the backend uses the existing OpenAI Responses integration for structured extraction.
- If it is unavailable, a conservative Bengali fallback parser handles common planting/input/land-change patterns.
- Unknown or ambiguous data is marked for confirmation instead of being invented.

## Privacy
All farm/farm-journal APIs are authenticated with the current user (`Depends(me)`) and query by that user ID. Farm details are not public profile data.

## Important unit note
Bangladesh land units can vary by locality. The current normalization uses 1 katha = 1.65 decimal and 1 bigha = 33 decimal as a platform baseline. Original unit/value is retained so this mapping can later be made region-specific without losing farmer input.
