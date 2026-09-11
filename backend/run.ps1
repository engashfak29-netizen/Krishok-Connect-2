$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
& powershell -ExecutionPolicy Bypass -File (Join-Path $root "START_KRISHOK_CONNECT.ps1")
