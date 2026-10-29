@echo off
cd /d "%~dp0"
title SitSmart IoT - Node 3: Detector & Dashboard Server
echo =========================================================
echo   SitSmart IoT - Menjalankan Detector & Dashboard Server
echo =========================================================
echo.
py detector.py
if errorlevel 1 (
    echo.
    echo Menjalankan dengan perintah python...
    python detector.py
)
echo.
pause
