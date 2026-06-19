# Django Project Setup Script
# Run this AFTER Python 3.12 is installed successfully

. (Join-Path $PSScriptRoot "_lib.ps1")
Set-ProjectRootLocation

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Django Project Setup" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Verify Python is installed
Write-Host "Checking Python installation..." -ForegroundColor Green
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  ✓ Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python not found!" -ForegroundColor Red
    Write-Host "  Please run scripts\install_python312.ps1 first" -ForegroundColor Yellow
    pause
    exit 1
}

# Check if we're in the correct directory
if (-not (Test-Path ".\requirements.txt")) {
    Write-Host "  ✗ requirements.txt not found!" -ForegroundColor Red
    Write-Host "  Could not find requirements.txt in the project root" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host ""
Write-Host "Step 1: Creating Virtual Environment..." -ForegroundColor Green
if (Test-Path ".\venv") {
    Write-Host "  Removing old virtual environment..." -ForegroundColor Yellow
    Remove-Item -Path ".\venv" -Recurse -Force
}

python -m venv venv
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "  ✗ Failed to create virtual environment" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "Step 2: Activating Virtual Environment..." -ForegroundColor Green
& .\venv\Scripts\Activate.ps1
Write-Host "  ✓ Virtual environment activated" -ForegroundColor Green

Write-Host ""
Write-Host "Step 3: Upgrading pip..." -ForegroundColor Green
python -m pip install --upgrade pip
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ pip upgraded" -ForegroundColor Green
} else {
    Write-Host "  ✗ pip upgrade failed" -ForegroundColor Red
}

Write-Host ""
Write-Host "Step 4: Installing project dependencies..." -ForegroundColor Green
Write-Host "  This may take several minutes..." -ForegroundColor Yellow
pip install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ All dependencies installed" -ForegroundColor Green
} else {
    Write-Host "  ✗ Some dependencies failed to install" -ForegroundColor Red
    Write-Host "  Check the errors above" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Step 5: Running Django Migrations..." -ForegroundColor Green
python manage.py makemigrations
python manage.py migrate

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Migrations completed" -ForegroundColor Green
} else {
    Write-Host "  ✗ Migrations failed" -ForegroundColor Red
}

Write-Host ""
Write-Host "Step 6: Collecting Static Files..." -ForegroundColor Green
python manage.py collectstatic --noinput 2>$null
Write-Host "  ✓ Static files collected" -ForegroundColor Green

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your Django project is ready!" -ForegroundColor Green
Write-Host ""
Write-Host "To run the development server:" -ForegroundColor Yellow
Write-Host "  1. Make sure virtual environment is active (venv)" -ForegroundColor White
Write-Host "  2. Run: python manage.py runserver" -ForegroundColor White
Write-Host ""
Write-Host "To activate virtual environment in future:" -ForegroundColor Yellow
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
pause
