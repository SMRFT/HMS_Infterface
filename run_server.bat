@echo off
title HMS Server [Port 1310]
cd /d "%~dp0"

:loop
echo =======================================================
echo [%date% %time%] Starting Django Server on 0.0.0.0:1310...
echo =======================================================
py -3.11 manage.py runserver 0.0.0.0:1310
echo.
echo [WARNING] Django Server stopped. Restarting in 3 seconds...
timeout /t 3 /nobreak >nul
goto loop
