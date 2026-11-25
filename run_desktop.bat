@echo off
title Hand Tracking AI Studio - Desktop Mode
cd /d "%~dp0"

echo ========================================================
echo    Hand Tracking AI Studio - Running Desktop App
echo ========================================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" desktop_app.py
) else (
    python desktop_app.py
)

pause
