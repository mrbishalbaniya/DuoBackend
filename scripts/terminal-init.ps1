# Prepends DuoBackend venv to PATH so `python manage.py runserver` works.
$ErrorActionPreference = "SilentlyContinue"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$VenvScripts = Join-Path $ProjectRoot "venv\Scripts"

if (Test-Path (Join-Path $VenvScripts "python.exe")) {
    $env:PATH = "$VenvScripts;$env:PATH"
    Set-Location $ProjectRoot
    Write-Host "DuoBackend venv active — run: python manage.py runserver 8001" -ForegroundColor Cyan
} else {
    Set-Location $ProjectRoot
    Write-Host "venv missing. Run: .\scripts\install-deps.ps1" -ForegroundColor Red
}
