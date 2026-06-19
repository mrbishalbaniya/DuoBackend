@echo off
echo ========================================
echo Python 3.12 Complete Setup
echo ========================================
echo.
echo This will:
echo - Remove all old Python installations
echo - Install Python 3.12
echo - Setup environment variables
echo - Install Django project dependencies
echo.
echo IMPORTANT: This must run as Administrator!
echo.
pause

powershell -ExecutionPolicy Bypass -File "%~dp0complete_python_setup.ps1"

pause
