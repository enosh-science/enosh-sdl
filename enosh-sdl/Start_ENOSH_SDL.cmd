@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
 set "PY=py -3"
) else (
 where python >nul 2>&1
 if errorlevel 1 (
  echo Please install Python 3.10+ from python.org and check Add Python to PATH.
  pause
  exit /b 1
 )
 set "PY=python"
)
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8765/'"
%PY% -m enosh_sdl.server --port 8765
pause
