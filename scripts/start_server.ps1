# Django Server Startup Script
# This script activates the virtual environment and starts the Django server

. (Join-Path $PSScriptRoot "_lib.ps1")
Set-ProjectRootLocation

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Starting Django Server" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "✗ ERROR: Virtual environment not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please run setup first:" -ForegroundColor Yellow
    Write-Host "  .\scripts\complete_python_setup.ps1" -ForegroundColor White
    Write-Host ""
    pause
    exit 1
}

# Check if Django is installed
$djangoCheck = .\venv\Scripts\pip.exe show django 2>&1
if ($djangoCheck -notmatch "Version:") {
    Write-Host "✗ ERROR: Django not installed in virtual environment!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install dependencies:" -ForegroundColor Yellow
    Write-Host "  .\venv\Scripts\activate" -ForegroundColor White
    Write-Host "  pip install -r requirements.txt" -ForegroundColor White
    Write-Host ""
    pause
    exit 1
}

Write-Host "✓ Virtual environment found" -ForegroundColor Green
Write-Host "✓ Django installed" -ForegroundColor Green
Write-Host ""
Write-Host "Starting Django development server..." -ForegroundColor Yellow
Write-Host "Server will be available at: http://127.0.0.1:8001" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host ""

# Activate virtual environment and run server
& .\venv\Scripts\python.exe manage.py runserver 8001
