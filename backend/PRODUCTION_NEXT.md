# Next implementation

Implemented in this build:
- Admin dashboard APIs and UI
- Account password change and self-delete
- Seller order list
- Product reviews with delivered-order verification
- WebRTC signaling websocket (`/ws/calls/{room_id}`); audio/video media remains peer-to-peer
- Order detail authorization

External credentials still required for production payment/SMS. The server intentionally does not fake payment success.


## NEXT4 completed
- Session revocation is now enforced on every authenticated REST request.
- Order status transitions are role-aware for buyers/sellers/admins.
- Added `create_admin.py` one-time admin bootstrap CLI.
- Fixed chat WebSocket token key and API-host derivation.
- Added buyer/seller order management page.
- Added product review display.

## NEXT5
- Seller dashboard added with order KPIs and status controls.
- Payment transaction abstraction added for bKash/Nagad initiation; provider credentials/callback verification remain production configuration work.
- Individual notification read endpoint added.
