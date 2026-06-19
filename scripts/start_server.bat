@echo off
cd /d "%~dp0\.."
REM Simple Django Server Starter
REM Double-click this file to start the server

echo ==========================================
echo Starting Django Server
echo ==========================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo ERROR: Virtual environment not found!
    echo.
    echo Please run: scripts\RUN_ME_AS_ADMIN.bat first
    echo.
    pause
    exit /b 1
)

echo Starting server...
echo.
echo Server will be available at: http://127.0.0.1:8001
echo.
echo Press Ctrl+C to stop the server
echo.

REM Run server using venv Python
venv\Scripts\python.exe manage.py runserver 8001

pause
