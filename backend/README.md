# Krishok Connect Backend

FastAPI + SQLite backend for Krishok Connect.

## Features
- JWT authentication and persistent sessions
- Users, profiles, follow system
- Posts, likes, comments
- Marketplace, cart, checkout and order lifecycle
- Conversations and persistent messages
- Notifications and reports
- Market-price API
- Real weather API proxy using Open-Meteo (15-minute cache)
- Authenticated image/video upload endpoint (`/media`)
- Optional local Ollama AI endpoint (`/api/v1/ai/chat`) with safe fallback

## Run on Windows
```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY='replace-with-a-random-secret'
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Open `http://127.0.0.1:8000/docs`.

## Frontend
Set `KC_API_BASE` in browser localStorage to the backend URL, or use the default `http://127.0.0.1:8000`.

## AI
If Ollama is running locally, set `OLLAMA_URL` and `OLLAMA_MODEL`. The application automatically falls back to built-in Bengali guidance when Ollama is unavailable.

## Production notes
Use PostgreSQL, object storage/CDN, HTTPS, a strong secret, restricted CORS, rate limiting, background jobs, and a real payment/SMS provider before public launch. Payment gateway credentials are intentionally not hard-coded.


## NEXT14–18
See `PRODUCTION_NEXT14_18.md` for weather/market, social, calls, admin analytics and security hardening.
