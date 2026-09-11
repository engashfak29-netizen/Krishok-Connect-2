# Krishok Connect — NEXT36–39 COMPLETE

## NEXT36 — Voice/Video Calling
- Authenticated call session table and lifecycle: ringing → connected → ended/rejected/missed/cancelled.
- Caller/callee authorization is enforced for call APIs and signaling rooms.
- WebRTC signaling over authenticated WebSocket; media remains peer-to-peer.
- Audio/video call controls in chat room: call, accept, reject, end.
- ICE candidate exchange and reconnect state handling.
- `Permissions-Policy` allows camera/microphone for same-origin use.
- TURN servers can be supplied through `window.KC_TURN_SERVERS` for production NAT traversal.

## NEXT37 — Advanced AI / Crop Intelligence
- Diagnosis accepts crop age, stage, variety, region, season, soil and weather context.
- Crop Intelligence management rules now filter by variety as well as age/stage/region/season.
- Verified structured diagnosis cases and approved knowledge remain higher-priority context.
- Pesticide/dose safety rule retained: no verified knowledge → label/local agriculture officer.
- OpenAI remains credential/configuration dependent; no fake success is generated.

## NEXT38 — Admin Control Center
- Existing Super Admin Control Center retained.
- Staff account lifecycle, roles, permission matrix, activation/deactivation, password reset and role removal remain backend-authorized.
- Department dashboards remain isolated by role/permission.
- Finance, Marketplace, AI Content, Crop Intelligence, Support and Moderation controls remain separated.
- Audit logging remains enabled for sensitive management actions.

## NEXT39 — Security / QA
- Python compilation and JavaScript syntax checks passed.
- Direct call-room membership authorization added.
- Session validation and disabled-staff checks retained.
- API rate limiting/security headers retained.
- Production secrets are configuration-only.
- Static security regression suite included as `verify_next36_39.py`.

### Production prerequisites
- HTTPS/WSS
- PostgreSQL
- Strong `SECRET_KEY`
- Real bKash/Nagad credentials/webhook secret
- Real SMS/Email provider
- TURN server credentials for reliable mobile calling
- `CORS_ORIGINS` restricted to production origins
