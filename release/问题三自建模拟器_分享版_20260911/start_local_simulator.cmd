@echo off
cd /d "%~dp0"
set "Q3PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%Q3PY%" (
  "%Q3PY%" simulator.py gui
  goto :done
)

where py >nul 2>nul
if not errorlevel 1 (
  py -3 simulator.py gui
  goto :done
)

where python >nul 2>nul
if not errorlevel 1 (
  python simulator.py gui
  goto :done
)

echo [ERROR] Python 3.10 or newer was not found.
echo Install Python, select "Add Python to PATH", then run this file again.
pause
exit /b 1

:done
if errorlevel 1 pause
