@echo off
title WALL-E & EVE Mission Control Launcher
color 0b

echo =========================================================
echo    WALL-E & EVE Autonomous POMDP Mission Control
echo =========================================================
echo.
echo [*] Initializing Python Virtual Environment...

:: Check if virtual environment exists
if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else (
    echo [!] Virtual environment not found in %~dp0venv.
    echo [*] Falling back to system Python...
    set "PYTHON_EXE=python"
)

:: Move into the folder where this batch file lives
cd /d "%~dp0"

echo [*] Starting FastAPI Backend on http://localhost:8000 ...
start /b "" "%PYTHON_EXE%" -m uvicorn server:app --host 127.0.0.1 --port 8000

:: Small delay to let the server start up
timeout /t 2 /nobreak >nul

echo [*] Launching Mission Control in your browser...
start http://localhost:8000

echo.
echo =========================================================
echo    SERVER RUNNING at http://localhost:8000
echo    Keep this window open while using the application.
echo    Press Ctrl+C or simply close this window to stop.
echo =========================================================
echo.

:: Keep window alive and monitor the server process
pause >nul
taskkill /f /im python.exe >nul 2>&1