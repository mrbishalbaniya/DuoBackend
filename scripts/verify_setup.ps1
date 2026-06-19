# Python Setup Verification Script
# Run this AFTER restarting your computer

. (Join-Path $PSScriptRoot "_lib.ps1")

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Python 3.12 Setup Verification" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$allGood = $true

# Test 1: Check if python command works
Write-Host "Test 1: Checking Python command..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1 | Out-String
    if ($pythonVersion -match "Python 3\.12") {
        Write-Host "  ✓ PASS: $($pythonVersion.Trim())" -ForegroundColor Green
    } else {
        Write-Host "  ✗ FAIL: Wrong version - $($pythonVersion.Trim())" -ForegroundColor Red
        $allGood = $false
    }
} catch {
    Write-Host "  ✗ FAIL: Python command not found" -ForegroundColor Red
    Write-Host "    Error: $($_.Exception.Message)" -ForegroundColor Red
    $allGood = $false
}

# Test 2: Check if pip works
Write-Host ""
Write-Host "Test 2: Checking pip command..." -ForegroundColor Yellow
try {
    $pipVersion = pip --version 2>&1 | Out-String
    if ($pipVersion -match "pip") {
        Write-Host "  ✓ PASS: $($pipVersion.Trim())" -ForegroundColor Green
    } else {
        Write-Host "  ✗ FAIL: pip not working correctly" -ForegroundColor Red
        $allGood = $false
    }
} catch {
    Write-Host "  ✗ FAIL: pip command not found" -ForegroundColor Red
    $allGood = $false
}

# Test 3: Check Python installation location
Write-Host ""
Write-Host "Test 3: Checking Python installation location..." -ForegroundColor Yellow
try {
    $pythonPath = (Get-Command python -ErrorAction Stop).Path
    Write-Host "  ✓ PASS: Python found at: $pythonPath" -ForegroundColor Green
    
    if ($pythonPath -like "*Python312*") {
        Write-Host "  ✓ Correct location (Python312)" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ WARNING: Python not in expected location" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ✗ FAIL: Cannot determine Python location" -ForegroundColor Red
    $allGood = $false
}

# Test 4: Check PATH environment variable
Write-Host ""
Write-Host "Test 4: Checking PATH environment variable..." -ForegroundColor Yellow
$systemPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$hasPython = $systemPath -match "Python312"
$hasScripts = $systemPath -match "Python312\\Scripts"

if ($hasPython) {
    Write-Host "  ✓ PASS: Python312 in System PATH" -ForegroundColor Green
} else {
    Write-Host "  ✗ FAIL: Python312 NOT in System PATH" -ForegroundColor Red
    $allGood = $false
}

if ($hasScripts) {
    Write-Host "  ✓ PASS: Python312\Scripts in System PATH" -ForegroundColor Green
} else {
    Write-Host "  ✗ FAIL: Python312\Scripts NOT in System PATH" -ForegroundColor Red
    $allGood = $false
}

# Test 5: Check if virtual environment exists
Write-Host ""
Write-Host "Test 5: Checking virtual environment..." -ForegroundColor Yellow
$venvPath = Join-Path $ProjectRoot "venv"

if (Test-Path $venvPath) {
    Write-Host "  ✓ PASS: Virtual environment exists" -ForegroundColor Green
    
    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    if (Test-Path $venvPython) {
        Write-Host "  ✓ PASS: Virtual environment Python found" -ForegroundColor Green
    } else {
        Write-Host "  ✗ FAIL: Virtual environment Python not found" -ForegroundColor Red
        $allGood = $false
    }
} else {
    Write-Host "  ✗ FAIL: Virtual environment not found" -ForegroundColor Red
    Write-Host "    Run: python -m venv venv" -ForegroundColor Yellow
    $allGood = $false
}

# Test 6: Check if Django is installed in venv
Write-Host ""
Write-Host "Test 6: Checking Django installation..." -ForegroundColor Yellow
if (Test-Path $venvPath) {
    try {
        $venvPip = Join-Path $venvPath "Scripts\pip.exe"
        $djangoCheck = & $venvPip show django 2>&1 | Out-String
        
        if ($djangoCheck -match "Version:") {
            $version = ($djangoCheck | Select-String "Version: (.+)").Matches.Groups[1].Value
            Write-Host "  ✓ PASS: Django $version installed in venv" -ForegroundColor Green
        } else {
            Write-Host "  ✗ FAIL: Django not installed in venv" -ForegroundColor Red
            Write-Host "    Run: .\venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
            $allGood = $false
        }
    } catch {
        Write-Host "  ✗ FAIL: Cannot check Django installation" -ForegroundColor Red
        $allGood = $false
    }
}

# Test 7: Check App Execution Aliases
Write-Host ""
Write-Host "Test 7: Checking App Execution Aliases..." -ForegroundColor Yellow
Write-Host "  ⚠ Manual check required:" -ForegroundColor Yellow
Write-Host "    1. Press Win + I to open Settings" -ForegroundColor Gray
Write-Host "    2. Go to: Apps > Advanced app settings > App execution aliases" -ForegroundColor Gray
Write-Host "    3. Verify python.exe and python3.exe are turned OFF" -ForegroundColor Gray

# Final Summary
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
if ($allGood) {
    Write-Host "✓ ALL TESTS PASSED!" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Your Python setup is working correctly!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Activate virtual environment:" -ForegroundColor White
    Write-Host "   .\venv\Scripts\activate" -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Run Django server:" -ForegroundColor White
    Write-Host "   python manage.py runserver" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "✗ SOME TESTS FAILED" -ForegroundColor Red
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Please fix the issues above." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Common fixes:" -ForegroundColor Yellow
    Write-Host "1. Restart your computer" -ForegroundColor White
    Write-Host "2. Disable App Execution Aliases in Settings" -ForegroundColor White
    Write-Host "3. Open a NEW PowerShell window" -ForegroundColor White
    Write-Host "4. Run setup script again if needed" -ForegroundColor White
    Write-Host ""
    Write-Host "For detailed help, see: scripts\docs\SETUP_INSTRUCTIONS.md" -ForegroundColor Cyan
    Write-Host ""
}

pause
