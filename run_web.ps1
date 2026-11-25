# Hand Tracking AI Studio - Web Dashboard Launcher
Set-Location -Path $PSScriptRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   Hand Tracking AI Studio - Launching Web Dashboard" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$PythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

Start-Process "http://localhost:8050"
& $PythonExe -m uvicorn main:app --host 127.0.0.1 --port 8050
