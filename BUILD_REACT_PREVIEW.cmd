@echo off
cd /d "%~dp0"
set /p WFS_PID=Masukkan ID project React/Vite (20 hex): 
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build-react-preview.ps1" -ProjectId "%WFS_PID%"
pause
