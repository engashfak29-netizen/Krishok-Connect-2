# Production checklist

Implemented in this build:
- JWT authentication and session records
- Persistent SQLite database
- REST APIs for users, social feed, marketplace, cart, orders, notifications and reports
- WebSocket real-time conversation channel
- Media upload endpoint
- Weather and Ollama integration
- Docker image/compose scaffolding

Before public deployment:
- Set a strong SECRET_KEY
- Set CORS_ORIGINS to the real frontend origin(s)
- Move DATABASE_URL to PostgreSQL and run a migration/SQLAlchemy layer before scale-out
- Put media on S3-compatible object storage/CDN
- Configure HTTPS/reverse proxy
- Configure real bKash/Nagad merchant credentials and callback verification
- Configure an SMS/OTP provider
- Add WebRTC TURN server for reliable calls
- Add rate limiting, malware scanning, backups and monitoring
- Load-test API/WebSocket endpoints
