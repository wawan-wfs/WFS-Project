@echo off
cd /d "%~dp0"
python scripts\operator-runner.py --list
if errorlevel 1 pause & exit /b 1
echo.
echo Copy a queued Job ID from above, then run:
echo python scripts\operator-runner.py --job JOB_ID
pause
