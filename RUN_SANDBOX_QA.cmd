@echo off
setlocal
cd /d "%~dp0"
echo WFS PROJECT - isolated Docker QA (operator only)
set /p PID=Paste Project ID (20 hex chars): 
where py >nul 2>nul
if not errorlevel 1 (
    py -3 scripts\sandbox-qa.py %PID%
) else (
    python scripts\sandbox-qa.py %PID%
)
if errorlevel 1 (echo QA FAILED - see report) else (echo QA PASSED - see dashboard)
pause
