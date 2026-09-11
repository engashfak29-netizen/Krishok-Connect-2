> **Current launch decision:** Payment gateway and OTP functionality are intentionally removed from the active build and deferred to a later phase.

# Krishok Connect — Frontend + Backend

## Run backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

API: `http://127.0.0.1:8000`
Docs: `http://127.0.0.1:8000/docs`

## Run frontend

Do not open HTML with `file://` when testing API integration. Serve the project directory with a local web server, for example:

```powershell
python -m http.server 5500
```

Then open `http://127.0.0.1:5500/auth.html`.

## API address

The frontend defaults to `http://127.0.0.1:8000`.
For another API host, set before loading the app:

```js
localStorage.setItem('KC_API_BASE', 'http://YOUR-PC-IP:8000');
```

## Implemented frontend integration

- Login / registration / logout
- JWT session handling
- Backend profile loading and editing
- Feed loading from API
- Like and comment persistence
- Post creation with image data
- Marketplace product loading/search
- Product creation
- Cart add/remove
- Checkout/order creation
- Persistent conversations and messages
- Follow/unfollow
- Notifications and mark-all-read
- Market-price loading
- Backend-first search
- Authentication redirect for protected pages

## External services still requiring provider credentials

Real bKash/Nagad payment gateway, SMS/OTP, weather provider, production AI/RAG, WebRTC voice/video infrastructure and production media storage/CDN require provider accounts/API credentials. The UI does not fake successful external transactions.
