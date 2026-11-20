@echo off
setlocal
cd /d "%~dp0"
echo CAUTION: this runs AI-generated FastAPI code within a network-disabled, limited Docker container.
set /p PID=Paste Project ID (20 hex chars): 
set /p CONSENT=Type RUN to consent (anything else cancels): 
if not "%CONSENT%"=="RUN" exit /b 1
where py >nul 2>nul
if not errorlevel 1 (
    py -3 scripts\sandbox-qa.py %PID% --runtime --accept-risk
) else (
    python scripts\sandbox-qa.py %PID% --runtime --accept-risk
)
pause
