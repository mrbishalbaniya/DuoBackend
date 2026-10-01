# Start Django using the project venv (use this instead of bare `python` on Windows).
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Python = Join-Path $Root "venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "Virtual env missing. Run: .\scripts\install-deps.ps1" -ForegroundColor Red
    exit 1
}

Set-Location $Root
# 0.0.0.0 lets a phone on the same Wi-Fi reach this PC; localhost:8000 still works.
& $Python manage.py runserver 0.0.0.0:8000
