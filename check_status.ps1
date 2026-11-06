# Status Diagnostic Script
Set-Location -Path $PSScriptRoot

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "       HMS Machine Interface Status Diagnostic" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Port 1310 Check
$portConns = Get-NetTCPConnection -LocalPort 1310 -State Listen -ErrorAction SilentlyContinue
if ($portConns) {
    $serverPid = $portConns[0].OwningProcess
    Write-Host "[ONLINE]  Django Server is LISTENING on port 1310 (PID: $serverPid)" -ForegroundColor Green
} else {
    Write-Host "[OFFLINE] Django Server is NOT listening on port 1310" -ForegroundColor Red
}

# 2. Automation Worker Check
$workers = Get-CimInstance Win32_Process -Filter "name like 'python%'" | Where-Object { $_.CommandLine -match 'automate_results' }
if ($workers) {
    $workerPids = ($workers | Select-Object -ExpandProperty ProcessId) -join ', '
    Write-Host "[ONLINE]  Automation Worker is RUNNING (PID: $workerPids)" -ForegroundColor Green
} else {
    Write-Host "[OFFLINE] Automation Worker is NOT running" -ForegroundColor Red
}

Write-Host ""
Write-Host "Checking Live Retry Queue in MongoDB..." -ForegroundColor Cyan
& py -3.11 -c "import os, sys, dotenv; dotenv.load_dotenv(); sys.path.insert(0, '.'); from machine import retry_service; s = retry_service.get_queue_summary(); print('  * Waiting Approval: ' + str(s.get('WAITING_APPROVAL', 0)) + ' | Retrying: ' + str(s.get('PENDING_RETRY', 0)) + ' | Failed: ' + str(s.get('FAILED_PERMANENT', 0)) + ' | Resolved: ' + str(s.get('RESOLVED', 0)))"

Write-Host ""
Write-Host "Web UI Dashboard: http://localhost:1310/manual-entry/" -ForegroundColor White
Write-Host "=======================================================" -ForegroundColor Cyan
