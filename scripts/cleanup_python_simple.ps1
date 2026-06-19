# Simple Python Cleanup Script
# Run as Administrator

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Python Cleanup Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: Run as Administrator!" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "Cleaning Python directories..." -ForegroundColor Green

$dirs = @(
    "$env:LOCALAPPDATA\Programs\Python",
    "$env:LOCALAPPDATA\Python",
    "C:\Program Files\Python312",
    "C:\Program Files\Python311",
    "C:\Python312"
)

foreach ($dir in $dirs) {
    if (Test-Path $dir) {
        Write-Host "Removing: $dir" -ForegroundColor Yellow
        try {
            Remove-Item -Path $dir -Recurse -Force -ErrorAction Stop
            Write-Host "  OK - Removed" -ForegroundColor Green
        } catch {
            Write-Host "  FAILED - $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "Cleaning PATH variables..." -ForegroundColor Green

# User PATH
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$cleaned = ($userPath -split ';' | Where-Object { $_ -notmatch 'Python' }) -join ';'
[Environment]::SetEnvironmentVariable("Path", $cleaned, "User")
Write-Host "  User PATH cleaned" -ForegroundColor Green

# System PATH
$systemPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$cleaned = ($systemPath -split ';' | Where-Object { $_ -notmatch 'Python' }) -join ';'
[Environment]::SetEnvironmentVariable("Path", $cleaned, "Machine")
Write-Host "  System PATH cleaned" -ForegroundColor Green

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Cleanup Done!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "1. Go to Settings, Apps, Advanced app settings, App execution aliases" -ForegroundColor White
Write-Host "2. Disable python.exe and pip.exe toggles" -ForegroundColor White
Write-Host "3. Restart computer" -ForegroundColor White
Write-Host "4. Run install_python312.ps1" -ForegroundColor White
Write-Host ""
pause
