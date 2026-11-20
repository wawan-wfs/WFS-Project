@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (py -3 scripts\operator-runner.py --cleanup-expired) else (python scripts\operator-runner.py --cleanup-expired)
if errorlevel 1 echo WFS preview cleanup failed. Check Docker Desktop.
pause
