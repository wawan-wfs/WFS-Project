@echo off
setlocal
cd /d "%~dp0"
echo =========================================
echo     WFS PROJECT - AI SOFTWARE HOUSE
 echo     START (Windows 10 / 11)
echo =========================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-windows.ps1"
if errorlevel 1 (
  echo [ERROR] Setup failed. Check Docker Desktop / Python and logs above.
) else (
  echo Open http://localhost:8080 in your browser.
)
pause
