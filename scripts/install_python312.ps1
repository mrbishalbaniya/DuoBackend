# Python 3.12 Installation Script
# Run this script as Administrator AFTER cleanup and restart

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Python 3.12.9 Automated Installation" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    pause
    exit 1
}

# Python 3.12.9 download URL
$pythonVersion = "3.12.9"
$downloadUrl = "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-amd64.exe"
$installerPath = "$env:TEMP\python-$pythonVersion-installer.exe"

Write-Host "Step 1: Downloading Python $pythonVersion..." -ForegroundColor Green
Write-Host "From: $downloadUrl" -ForegroundColor Gray
Write-Host ""

try {
    # Download Python installer
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $downloadUrl -OutFile $installerPath -UseBasicParsing
    Write-Host "  ✓ Download complete" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Download failed: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please download manually from:" -ForegroundColor Yellow
    Write-Host "https://www.python.org/downloads/" -ForegroundColor Cyan
    pause
    exit 1
}

Write-Host ""
Write-Host "Step 2: Installing Python $pythonVersion..." -ForegroundColor Green
Write-Host "Installation path: C:\Program Files\Python312" -ForegroundColor Gray
Write-Host ""

# Installation arguments
$installArgs = @(
    "/quiet",
    "InstallAllUsers=1",
    "PrependPath=1",
    "Include_test=0",
    "Include_doc=1",
    "Include_dev=1",
    "Include_exe=1",
    "Include_launcher=1",
    "Include_lib=1",
    "Include_pip=1",
    "Include_tcltk=1",
    "TargetDir=C:\Program Files\Python312",
    "AssociateFiles=1",
    "CompileAll=1",
    "SimpleInstall=1"
)

try {
    # Run installer
    $process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru
    
    if ($process.ExitCode -eq 0) {
        Write-Host "  ✓ Python $pythonVersion installed successfully!" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Installation failed with exit code: $($process.ExitCode)" -ForegroundColor Red
        pause
        exit 1
    }
} catch {
    Write-Host "  ✗ Installation error: $_" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "Step 3: Cleaning up installer..." -ForegroundColor Green
Remove-Item -Path $installerPath -Force -ErrorAction SilentlyContinue
Write-Host "  ✓ Cleanup complete" -ForegroundColor Green

Write-Host ""
Write-Host "Step 4: Updating Environment Variables..." -ForegroundColor Green

# Add Python to PATH if not already there
$pythonPath = "C:\Program Files\Python312"
$pythonScriptsPath = "C:\Program Files\Python312\Scripts"

$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$pathUpdated = $false

if ($machinePath -notlike "*$pythonPath*") {
    $newPath = "$pythonPath;$pythonScriptsPath;$machinePath"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "Machine")
    $pathUpdated = $true
    Write-Host "  ✓ Added Python to System PATH" -ForegroundColor Green
} else {
    Write-Host "  - Python already in PATH" -ForegroundColor Gray
}

# Refresh current session PATH
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

Write-Host ""
Write-Host "Step 5: Verifying Installation..." -ForegroundColor Green
Write-Host ""

# Wait a moment for PATH to update
Start-Sleep -Seconds 2

# Verify Python installation
try {
    $pythonVersionCheck = & "C:\Program Files\Python312\python.exe" --version 2>&1
    Write-Host "  Python Version: $pythonVersionCheck" -ForegroundColor Cyan
    
    $pipVersionCheck = & "C:\Program Files\Python312\Scripts\pip.exe" --version 2>&1
    Write-Host "  Pip Version: $pipVersionCheck" -ForegroundColor Cyan
    
    Write-Host ""
    Write-Host "  ✓ Installation verified successfully!" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Verification failed: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Installation Complete!" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "1. Close this PowerShell window" -ForegroundColor White
Write-Host "2. Open a NEW PowerShell window (close all existing ones)" -ForegroundColor White
Write-Host "3. Run: python --version" -ForegroundColor White
Write-Host "4. Run: pip --version" -ForegroundColor White
Write-Host "5. Navigate to your project and run: python -m venv venv" -ForegroundColor White
Write-Host ""
Write-Host "If PATH still shows old Python, restart your computer." -ForegroundColor Yellow
Write-Host ""
pause
