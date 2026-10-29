@echo off
cd /d "%~dp0"
title SitSmart IoT - Simulator Telemetri 2-Edge
echo =========================================================
echo   SitSmart IoT - Menjalankan Simulator Skenario Telemetri
echo =========================================================
echo.
py scripts\simulate.py
if errorlevel 1 (
    echo.
    echo Menjalankan dengan perintah python...
    python scripts\simulate.py
)
echo.
pause
