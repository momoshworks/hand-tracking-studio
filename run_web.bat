@echo off
title Hand Tracking AI Studio - Web Dashboard
cd /d "%~dp0"

echo ========================================================
echo    Hand Tracking AI Studio - Launching Web Dashboard
echo ========================================================
echo Opening browser at: http://localhost:8050

start "" "http://localhost:8050"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8050
) else (
    python -m uvicorn main:app --host 127.0.0.1 --port 8050
)

pause
