# Run Django on port 8001 (frontend expects http://localhost:8001/api)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")
Set-ProjectRootLocation

$python = Join-Path $ProjectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Virtual environment not found. Run scripts\install-deps.ps1 or scripts\setup_project.ps1 first."
}

& $python manage.py runserver 8001
