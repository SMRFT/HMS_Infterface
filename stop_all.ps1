# Stop all HMS Machine Interface Services
Set-Location -Path $PSScriptRoot

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "       Stopping HMS Machine Interface Services" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Stop process listening on Port 1310
$portConnections = Get-NetTCPConnection -LocalPort 1310 -ErrorAction SilentlyContinue
if ($portConnections) {
    $pids = $portConnections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $pids) {
        try {
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            Write-Host "[STOPPED] Terminated Django Server on Port 1310 (PID $p)" -ForegroundColor Green
        } catch {}
    }
} else {
    Write-Host "[INFO] No process listening on Port 1310" -ForegroundColor Gray
}

# 2. Stop automate_results worker process
$workers = Get-CimInstance Win32_Process -Filter "name like 'python%'" | Where-Object { $_.CommandLine -match 'automate_results' }
if ($workers) {
    foreach ($w in $workers) {
        try {
            Stop-Process -Id $w.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host "[STOPPED] Terminated Automation Worker (PID $($w.ProcessId))" -ForegroundColor Green
        } catch {}
    }
} else {
    Write-Host "[INFO] No Automation Worker process found" -ForegroundColor Gray
}

# 3. Close launcher cmd windows
$cmdWindows = Get-CimInstance Win32_Process -Filter "name = 'cmd.exe'" | Where-Object { 
    $_.CommandLine -match 'run_server.bat' -or $_.CommandLine -match 'run_worker.bat' -or
    $_.CommandLine -match 'HMS Server' -or $_.CommandLine -match 'HMS Automation Worker'
}
if ($cmdWindows) {
    foreach ($c in $cmdWindows) {
        try {
            Stop-Process -Id $c.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host "[CLOSED]  Closed launcher window (PID $($c.ProcessId))" -ForegroundColor Green
        } catch {}
    }
}

Write-Host ""
Write-Host "[COMPLETE] HMS Machine Interface services stopped." -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

