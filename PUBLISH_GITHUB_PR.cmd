@echo off
setlocal
cd /d "%~dp0"
echo WFS PROJECT - GitHub Publisher. Default: DRY RUN (no push).
set /p PID=Project ID (20 hex chars): 
set /p REPO=GitHub owner/repository: 
where py >nul 2>nul
if not errorlevel 1 (
 py -3 scripts\publish-github.py %PID% --repo %REPO%
) else (
 python scripts\publish-github.py %PID% --repo %REPO%
)
echo To publish, run manually with --publish after review.
pause
