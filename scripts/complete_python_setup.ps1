# Complete Python Setup Script - Run as Administrator
# This script will: Clean up old Python, Install Python 3.12, Setup environment variables, Install project dependencies

param(
    [switch]$SkipCleanup = $false,
    [switch]$SkipInstall = $false
)

$ErrorActionPreference = "Continue"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Complete Python 3.12 Setup Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    pause
    exit 1
}

# ================ STEP 1: CLEANUP ================
if (-not $SkipCleanup) {
    Write-Host ""
    Write-Host "STEP 1: Cleaning up old Python installations..." -ForegroundColor Green
    Write-Host "-----------------------------------------------" -ForegroundColor Gray

    # Stop any Python processes
    Write-Host "Stopping Python processes..." -ForegroundColor Yellow
    Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2

    # Remove Python directories
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
        "C:\Python311",
        "C:\Python310"
    )

    foreach ($dir in $pythonDirs) {
        if (Test-Path $dir) {
            Write-Host "  Removing: $dir" -ForegroundColor Yellow
            try {
                Remove-Item -Path $dir -Recurse -Force -ErrorAction Stop
                Write-Host "    ✓ Removed successfully" -ForegroundColor Green
            } catch {
                Write-Host "    ✗ Failed: $($_.Exception.Message)" -ForegroundColor Red
            }
        }
    }

    # Clean PATH variables
    Write-Host ""
    Write-Host "Cleaning PATH environment variables..." -ForegroundColor Yellow

    # User PATH
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath) {
        $cleanedUserPath = ($userPath -split ';' | Where-Object { 
            $_ -and $_ -notmatch 'Python' -and $_ -notmatch 'pip'
        } | Select-Object -Unique) -join ';'
        [Environment]::SetEnvironmentVariable("Path", $cleanedUserPath, "User")
        Write-Host "  ✓ User PATH cleaned" -ForegroundColor Green
    }

    # System PATH
    $systemPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if ($systemPath) {
        $cleanedSystemPath = ($systemPath -split ';' | Where-Object { 
            $_ -and $_ -notmatch 'Python' -and $_ -notmatch 'pip'
        } | Select-Object -Unique) -join ';'
        [Environment]::SetEnvironmentVariable("Path", $cleanedSystemPath, "Machine")
        Write-Host "  ✓ System PATH cleaned" -ForegroundColor Green
    }

    # Clean Registry (optional)
    Write-Host ""
    Write-Host "Cleaning registry entries..." -ForegroundColor Yellow
    $regPaths = @(
        "HKCU:\Software\Python",
        "HKLM:\Software\Python",
        "HKLM:\Software\Wow6432Node\Python"
    )

    foreach ($regPath in $regPaths) {
        if (Test-Path $regPath) {
            try {
                Remove-Item -Path $regPath -Recurse -Force -ErrorAction Stop
                Write-Host "  ✓ Removed: $regPath" -ForegroundColor Green
            } catch {
                Write-Host "  ✗ Failed: $regPath" -ForegroundColor Red
            }
        }
    }

    Write-Host ""
    Write-Host "✓ Cleanup completed!" -ForegroundColor Green
}

# ================ STEP 2: INSTALL PYTHON 3.12 ================
if (-not $SkipInstall) {
    Write-Host ""
    Write-Host "STEP 2: Installing Python 3.12..." -ForegroundColor Green
    Write-Host "-----------------------------------------------" -ForegroundColor Gray

    $pythonVersion = "3.12.8"
    $pythonInstaller = "python-$pythonVersion-amd64.exe"
    $downloadUrl = "https://www.python.org/ftp/python/$pythonVersion/$pythonInstaller"
    $installerPath = "$env:TEMP\$pythonInstaller"
    $installPath = "C:\Python312"

    # Download Python installer
    Write-Host "Downloading Python $pythonVersion..." -ForegroundColor Yellow
    try {
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $downloadUrl -OutFile $installerPath -UseBasicParsing
        Write-Host "  ✓ Download completed" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ Download failed: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host ""
        Write-Host "Manual download required:" -ForegroundColor Yellow
        Write-Host "  1. Go to: https://www.python.org/downloads/" -ForegroundColor White
        Write-Host "  2. Download Python 3.12.8 (64-bit)" -ForegroundColor White
        Write-Host "  3. Run installer with options: Install for all users, Add to PATH, Install pip" -ForegroundColor White
        pause
        exit 1
    }

    # Install Python
    Write-Host ""
    Write-Host "Installing Python 3.12..." -ForegroundColor Yellow
    Write-Host "  (This may take a few minutes)" -ForegroundColor Gray

    $installArgs = @(
        "/quiet",
        "InstallAllUsers=1",
        "PrependPath=1",
        "Include_pip=1",
        "Include_test=0",
        "TargetDir=$installPath"
    )

    try {
        Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -NoNewWindow
        Write-Host "  ✓ Python installed to: $installPath" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ Installation failed: $($_.Exception.Message)" -ForegroundColor Red
        pause
        exit 1
    }

    # Clean up installer
    Remove-Item -Path $installerPath -Force -ErrorAction SilentlyContinue

    # ================ STEP 3: SETUP ENVIRONMENT VARIABLES ================
    Write-Host ""
    Write-Host "STEP 3: Setting up environment variables..." -ForegroundColor Green
    Write-Host "-----------------------------------------------" -ForegroundColor Gray

    $pythonPaths = @(
        "$installPath",
        "$installPath\Scripts"
    )

    # Get current System PATH
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $pathArray = $currentPath -split ';' | Where-Object { $_ }

    # Add Python paths if not already present
    $updated = $false
    foreach ($pythonPath in $pythonPaths) {
        if ($pathArray -notcontains $pythonPath) {
            $pathArray = @($pythonPath) + $pathArray
            $updated = $true
            Write-Host "  ✓ Added to PATH: $pythonPath" -ForegroundColor Green
        } else {
            Write-Host "  ○ Already in PATH: $pythonPath" -ForegroundColor Gray
        }
    }

    if ($updated) {
        $newPath = $pathArray -join ';'
        [Environment]::SetEnvironmentVariable("Path", $newPath, "Machine")
        Write-Host ""
        Write-Host "  ✓ System PATH updated" -ForegroundColor Green
    }

    # Update current session PATH
    $env:Path = "$installPath;$installPath\Scripts;" + $env:Path

    # Verify installation
    Write-Host ""
    Write-Host "Verifying Python installation..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2

    try {
        $pythonVersion = & "$installPath\python.exe" --version 2>&1
        Write-Host "  ✓ $pythonVersion" -ForegroundColor Green
        
        $pipVersion = & "$installPath\python.exe" -m pip --version 2>&1
        Write-Host "  ✓ $pipVersion" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ Verification failed" -ForegroundColor Red
        Write-Host "  Python may not be installed correctly" -ForegroundColor Yellow
    }
}

# ================ STEP 4: SETUP PROJECT ================
Write-Host ""
Write-Host "STEP 4: Setting up Django project..." -ForegroundColor Green
Write-Host "-----------------------------------------------" -ForegroundColor Gray

$projectPath = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectPath

# Remove old virtual environment
if (Test-Path "venv") {
    Write-Host "Removing old virtual environment..." -ForegroundColor Yellow
    Remove-Item -Path "venv" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  ✓ Removed old venv" -ForegroundColor Green
}

# Create new virtual environment
Write-Host ""
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
try {
    & python -m venv venv
    Write-Host "  ✓ Virtual environment created" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Failed to create venv: $($_.Exception.Message)" -ForegroundColor Red
    pause
    exit 1
}

# Activate virtual environment and install packages
Write-Host ""
Write-Host "Installing Django and project dependencies..." -ForegroundColor Yellow
Write-Host "  (This may take several minutes)" -ForegroundColor Gray

$venvPython = ".\venv\Scripts\python.exe"
$venvPip = ".\venv\Scripts\pip.exe"

# Upgrade pip first
Write-Host ""
Write-Host "Upgrading pip..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip --quiet

# Install packages from requirements.txt
Write-Host "Installing requirements..." -ForegroundColor Yellow
try {
    & $venvPip install -r requirements.txt --quiet
    Write-Host "  ✓ All packages installed successfully" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Some packages may have installation issues" -ForegroundColor Yellow
    Write-Host "  Attempting to install core packages..." -ForegroundColor Yellow
    
    # Install core Django packages
    $corePackages = @(
        "Django",
        "djangorestframework",
        "django-cors-headers",
        "djangorestframework-simplejwt",
        "pillow",
        "python-decouple",
        "channels",
        "daphne"
    )
    
    foreach ($pkg in $corePackages) {
        Write-Host "  Installing $pkg..." -ForegroundColor Gray
        & $venvPip install $pkg --quiet
    }
}

# ================ FINAL STEPS ================
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Python 3.12 has been installed and configured." -ForegroundColor Green
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. DISABLE APP EXECUTION ALIASES:" -ForegroundColor White
Write-Host "   - Press Win + I to open Settings" -ForegroundColor Gray
Write-Host "   - Go to: Apps > Advanced app settings > App execution aliases" -ForegroundColor Gray
Write-Host "   - Turn OFF toggles for 'python.exe' and 'python3.exe'" -ForegroundColor Gray
Write-Host ""
Write-Host "2. RESTART YOUR COMPUTER to apply PATH changes" -ForegroundColor White
Write-Host ""
Write-Host "3. After restart, verify installation:" -ForegroundColor White
Write-Host "   python --version" -ForegroundColor Gray
Write-Host "   pip --version" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Run your Django server:" -ForegroundColor White
Write-Host "   .\\venv\\Scripts\\activate" -ForegroundColor Gray
Write-Host "   python manage.py runserver" -ForegroundColor Gray
Write-Host ""

pause
