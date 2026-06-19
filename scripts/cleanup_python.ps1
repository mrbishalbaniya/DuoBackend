# Python Cleanup and Reinstallation Script
# Run this script as Administrator

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Python Complete Cleanup Script" -ForegroundColor Cyan
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

Write-Host "Step 1: Listing all Python installations..." -ForegroundColor Green
Write-Host ""

# Find all Python installations
$pythonApps = Get-WmiObject -Class Win32_Product | Where-Object { $_.Name -like "*Python*" }

if ($pythonApps.Count -eq 0) {
    Write-Host "No Python installations found via Win32_Product" -ForegroundColor Yellow
} else {
    Write-Host "Found Python installations:" -ForegroundColor Cyan
    foreach ($app in $pythonApps) {
        Write-Host "  - $($app.Name) (Version: $($app.Version))" -ForegroundColor White
    }
}

Write-Host ""
Write-Host "Step 2: Uninstalling Python packages..." -ForegroundColor Green

# Uninstall each Python installation
foreach ($app in $pythonApps) {
    Write-Host "Uninstalling: $($app.Name)..." -ForegroundColor Yellow
    try {
        $app.Uninstall() | Out-Null
        Write-Host "  ✓ Successfully uninstalled $($app.Name)" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ Failed to uninstall $($app.Name): $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Step 3: Cleaning up Python directories..." -ForegroundColor Green

# Common Python installation directories
$pythonDirs = @(
    "$env:LOCALAPPDATA\Programs\Python",
    "$env:LOCALAPPDATA\Python",
    "$env:APPDATA\Python",
    "C:\Program Files\Python312",
    "C:\Program Files\Python311",
    "C:\Program Files\Python310",
    "C:\Program Files (x86)\Python312",
    "C:\Program Files (x86)\Python311",
    "C:\Python312",
    "C:\Python311"
)

foreach ($dir in $pythonDirs) {
    if (Test-Path $dir) {
        Write-Host "Removing directory: $dir" -ForegroundColor Yellow
        try {
            Remove-Item -Path $dir -Recurse -Force -ErrorAction Stop
            Write-Host "  ✓ Removed $dir" -ForegroundColor Green
        } catch {
            Write-Host "  X Failed to remove $dir" -ForegroundColor Red
            Write-Host "    Error: $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "    You may need to close applications using Python files" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "Step 4: Cleaning Environment Variables (PATH)..." -ForegroundColor Green

# Clean User PATH
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$userPathArray = $userPath -split ';'
$cleanedUserPath = $userPathArray | Where-Object { $_ -notmatch 'Python' }
$newUserPath = $cleanedUserPath -join ';'

if ($userPath -ne $newUserPath) {
    [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
    Write-Host "  ✓ Cleaned User PATH" -ForegroundColor Green
} else {
    Write-Host "  - No Python entries found in User PATH" -ForegroundColor Gray
}

# Clean System PATH
$systemPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$systemPathArray = $systemPath -split ';'
$cleanedSystemPath = $systemPathArray | Where-Object { $_ -notmatch 'Python' }
$newSystemPath = $cleanedSystemPath -join ';'

if ($systemPath -ne $newSystemPath) {
    [Environment]::SetEnvironmentVariable("Path", $newSystemPath, "Machine")
    Write-Host "  ✓ Cleaned System PATH" -ForegroundColor Green
} else {
    Write-Host "  - No Python entries found in System PATH" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Step 5: Removing Python Registry Entries..." -ForegroundColor Green

# Registry paths to clean
$registryPaths = @(
    "HKCU:\Software\Python",
    "HKLM:\Software\Python",
    "HKLM:\Software\Wow6432Node\Python"
)

foreach ($regPath in $registryPaths) {
    if (Test-Path $regPath) {
        Write-Host "Removing registry key: $regPath" -ForegroundColor Yellow
        try {
            Remove-Item -Path $regPath -Recurse -Force -ErrorAction Stop
            Write-Host "  ✓ Removed $regPath" -ForegroundColor Green
        } catch {
            Write-Host "  X Failed to remove $regPath" -ForegroundColor Red
            Write-Host "    Error: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Cleanup Complete!" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT NEXT STEPS:" -ForegroundColor Yellow
Write-Host "1. Go to Settings, then Apps, then Advanced app settings, then App execution aliases" -ForegroundColor White
Write-Host "2. Disable python.exe, python3.exe, pip.exe toggles" -ForegroundColor White
Write-Host "3. Restart your computer" -ForegroundColor White
Write-Host "4. Run the install_python312.ps1 script" -ForegroundColor White
Write-Host ""
pause
