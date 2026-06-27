@echo off
title VAYU Launcher
cd /d "%~dp0"

set PYTHONIOENCODING=utf-8
chcp 65001 >nul

echo ========================================
echo    VAYU - AI Assistant
echo ========================================
echo.

echo [1/3] Installing/updating dependencies...
python -m pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [!] pip install failed. Check your internet connection.
    pause
    exit /b 1
)

echo [2/3] Setting up Playwright browsers...
python -m playwright install chromium 2>nul
if %errorlevel% neq 0 (
    echo [!] Playwright setup failed (non-critical - browser features may be limited)
)

echo [3/3] Launching VAYU...
echo.
python main.py

echo.
echo VAYU has exited.
pause
