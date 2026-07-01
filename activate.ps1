# Activate DuoBackend venv so `python manage.py runserver` works.
$ProjectRoot = $PSScriptRoot
$VenvScripts = Join-Path $ProjectRoot "venv\Scripts"

if (-not (Test-Path (Join-Path $VenvScripts "python.exe"))) {
    Write-Error "Run .\scripts\install-deps.ps1 first to create venv."
}

$env:PATH = "$VenvScripts;$env:PATH"
Set-Location $ProjectRoot
