@echo off
cd /d "%~dp0\.."
if not exist "venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo Run scripts\install-deps.ps1 or scripts\setup_project.ps1 first.
    pause
    exit /b 1
)
venv\Scripts\python.exe manage.py runserver 8001
