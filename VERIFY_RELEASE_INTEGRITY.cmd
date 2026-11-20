@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 scripts\verify-release.py
) else (
  where python >nul 2>&1
  if %errorlevel%==0 (
    python scripts\verify-release.py
  ) else (
    echo Python 3 tidak tersedia. Jalankan di komputer dengan Python 3 terpasang.
    exit /b 1
  )
)
if %errorlevel% neq 0 (
  echo Integritas source tidak valid. Ekstrak ulang ZIP dari sumber tepercaya.
  exit /b 1
)
endlocal
