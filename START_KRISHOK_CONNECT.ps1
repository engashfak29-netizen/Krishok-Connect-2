$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== Krishok Connect ONE-CLICK START ===" -ForegroundColor Green

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  throw "Python is not installed or not available on PATH. Install Python 3.14+ and run this file again."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  Write-Host "[1/4] Creating virtual environment..."
  & python -m venv .venv
  if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
}

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
Write-Host "[2/4] Installing verified Python dependencies..."
& $venvPy -m pip install --upgrade pip --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed. Nothing was started." }
& $venvPy -m pip install --prefer-binary --disable-pip-version-check -r ".\backend\requirements.txt"
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. The server was NOT started." }

Write-Host "[3/4] Running startup checks..."
Push-Location ".\backend"
& $venvPy -m compileall -q ".\app"
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Python compile check failed." }

$env:DATABASE_URL = if ($env:DATABASE_URL) { $env:DATABASE_URL } else { "sqlite:///./krishok_connect.db" }
$env:ENVIRONMENT = if ($env:ENVIRONMENT) { $env:ENVIRONMENT } else { "development" }
$env:ENABLE_API_DOCS = if ($env:ENABLE_API_DOCS) { $env:ENABLE_API_DOCS } else { "true" }

& $venvPy -c "import app.main; print('Backend import: PASS')"
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Backend import failed. The server was NOT started." }

Write-Host "[4/4] Starting Krishok Connect..."
Write-Host ""
Write-Host "Open: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "API:  http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow
& $venvPy -m uvicorn app.main:app --host 0.0.0.0 --port 8000
$code=$LASTEXITCODE
Pop-Location
exit $code
