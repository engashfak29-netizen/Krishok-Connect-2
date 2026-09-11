# Krishok Connect — Final Completion Package

## Completed in this pass

### 1. Farmer system
- Farm → Plot → Crop → Journal is now the source of truth.
- Legacy `/api/v1/farmer/crops` endpoints are compatibility adapters into `plot_crops`; they no longer maintain a second active crop database.
- Old crop-profile data is migrated into the unified model when the API starts.
- Farm history remains non-destructive.
- Journal changes create farm events and preserve journal history.
- Farmer AI context is assembled from farm, active plots/crops, activities, inputs and journal history.

### 2. AI
- Farmer chat automatically receives the private farm context when available.
- Crop/variety/stage/region/soil/weather context remains supported by Crop Intelligence and diagnosis.
- Approved knowledge retrieval remains the authoritative RAG source.
- AI is instructed not to invent pesticide dose or unverified agricultural facts.

### 3. Chat + calling
- Conversation messages have delivered/read timestamps.
- Read endpoint added.
- Image attachment sending is available through the media upload endpoint.
- Typing state is relayed over WebSocket.
- Chat reconnects automatically.
- Calling supports server-provided TURN configuration and one ICE restart attempt after connection failure/disconnect.

### 4. Marketplace
- Checkout inventory reservations are written to the inventory ledger atomically.
- Seller payment accounts support bKash/Nagad/Rocket/Bank information.
- Seller order-payment reporting exists for direct merchant/COD workflows.
- Delivery tracking, order timeline and return workflow remain available.
- Platform payout creation is disabled unless `PLATFORM_SETTLEMENT_ENABLED=true`.

### 5. Initial-launch payment policy
- `REAL_PAYMENT_ENABLED=false` by default.
- Initial checkout is COD only.
- Seller subscription remains free when `SELLER_SUBSCRIPTION_FREE=true`.
- Seller direct payment information remains active.
- Future gateway/payment code remains present but cannot be accidentally activated without configuration.
- Management OTP security remains available; ordinary public account verification remains off by default through `REQUIRE_ACCOUNT_VERIFICATION=false`.

### 6. Production configuration
Set these on the real server when applicable:

- `DATABASE_URL` — production PostgreSQL
- `SECRET_KEY` — long random secret
- `CORS_ORIGINS` — exact production origins
- `OPENAI_API_KEY` — required for production OpenAI AI features
- `OPENAI_MODEL` — desired supported model
- `TURN_SERVERS_JSON` — TURN/STUN configuration for difficult networks
- `REAL_PAYMENT_ENABLED=true` only when real gateway integration is intentionally activated
- `PLATFORM_SETTLEMENT_ENABLED=true` only when platform settlement/commission is intentionally activated
- `SMS_OTP_URL` / `EMAIL_OTP_URL` only when OTP is intentionally activated

Never commit production secrets.

## What cannot be truthfully certified inside this offline build environment
The code/package is prepared for production, but these external facts require the actual deployment environment:

- real PostgreSQL connection
- real OpenAI API credentials/quota
- real SMS/email provider delivery
- real TURN server connectivity
- real HTTPS/domain
- real Android/browser camera/microphone permissions
- real load/stress capacity of the selected server
- real backup/restore execution against production storage

These are deployment/provisioning tests, not missing application architecture.
