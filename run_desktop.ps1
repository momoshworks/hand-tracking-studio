# Hand Tracking AI Studio - Desktop Mode Launcher
Set-Location -Path $PSScriptRoot

Write-Host "========================================================" -ForegroundColor Green
Write-Host "   Hand Tracking AI Studio - Running Desktop App" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green

$PythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

& $PythonExe desktop_app.py
