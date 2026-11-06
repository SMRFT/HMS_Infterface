# HMS Machine Interface PowerShell Launcher
Set-Location -Path $PSScriptRoot

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "       HMS Machine Interface Launcher (PowerShell)" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verify Python 3.11
$pyVer = & py -3.11 --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Python 3.11 was not found via 'py -3.11'." -ForegroundColor Red
    return
}
Write-Host "[INFO] Detected Python: $pyVer" -ForegroundColor Green

# 2. Ensure logs folder
if (!(Test-Path -Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

Write-Host "Starting Services..." -ForegroundColor Cyan

# 3. Start Django Server on Port 1310
Write-Host "[1/2] Starting Django Server on 0.0.0.0:1310..." -ForegroundColor Yellow
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "`"$PSScriptRoot\run_server.bat`""

Start-Sleep -Seconds 2

# 4. Start Automation Worker with Supervisor
Write-Host "[2/2] Starting Automation Worker with Auto-Restart..." -ForegroundColor Yellow
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "`"$PSScriptRoot\run_worker.bat`""

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "[SUCCESS] Both services launched successfully!" -ForegroundColor Green
Write-Host "  * Server URL  : http://localhost:1310/" -ForegroundColor White
Write-Host "  * Web UI URL  : http://localhost:1310/manual-entry/" -ForegroundColor White
Write-Host "  * Health check: Run .\status.bat" -ForegroundColor Gray
Write-Host "  * To stop     : Run .\stop_all.bat" -ForegroundColor Gray
Write-Host "=======================================================" -ForegroundColor Cyan
