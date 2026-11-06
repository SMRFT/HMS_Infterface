@echo off
setlocal
cd /d "%~dp0"

echo =======================================================
echo        HMS Machine Interface Launcher (Windows)
echo =======================================================
echo.

:: 1. Verify Python 3.11
py -3.11 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.11 was not found via 'py -3.11'.
    echo Please ensure Python 3.11 is installed.
    pause
    exit /b 1
)

:: 2. Ensure logs folder exists
if not exist logs mkdir logs

echo Starting Services...
echo.

:: 3. Start Django Server on Port 1310 in dedicated window
echo [1/2] Starting Django Server on 0.0.0.0:1310...
start "HMS Server [Port 1310]" "%~dp0run_server.bat"

:: Brief wait before launching worker
timeout /t 2 /nobreak >nul

:: 4. Start Automation Worker with Auto-Restart Supervisor
echo [2/2] Starting Automation Worker with Crash-Guard...
start "HMS Automation Worker" "%~dp0run_worker.bat"

echo.
echo =======================================================
echo [SUCCESS] Both services have been launched!
echo.
echo   * Django Server : http://localhost:1310/
echo   * Web UI Dashboard : http://localhost:1310/manual-entry/
echo   * Automation Worker : Running & monitoring approval queue
echo.
echo To check health: Run 'status.bat'
echo To stop services: Run 'stop_all.bat'
echo =======================================================
echo.
timeout /t 5
