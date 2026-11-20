@echo off
cd /d "%~dp0"
set /p WFS_PID=Masukkan Project ID 20 karakter dari dashboard: 
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\runtime-qa.ps1" -ProjectId "%WFS_PID%"
if errorlevel 1 (echo Sandbox QA FAILED) else (echo Sandbox QA finished)
pause
