# Krishok Connect — One-Click Launch

This package is prepared for local/demo launch on Windows.

## One command

Open PowerShell in this project root and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\START_KRISHOK_CONNECT.ps1
```

The launcher:
1. creates `.venv` if needed;
2. installs the Python dependencies from `backend/requirements.txt`;
3. compiles the backend;
4. imports the FastAPI application;
5. starts the API and serves the PWA/frontend from the same port.

Open `http://127.0.0.1:8000`.

The first run can take time because dependencies are installed. Subsequent runs reuse `.venv`.

If dependency installation fails, the launcher stops and does not falsely claim that the server started.
