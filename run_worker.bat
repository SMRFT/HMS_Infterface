@echo off
title HMS Automation Worker
cd /d "%~dp0"

:loop
echo =======================================================
echo [%date% %time%] Starting Automation & Retry Worker...
echo =======================================================
py -3.11 manage.py automate_results
echo.
echo [WARNING] Worker exited or stopped. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop

