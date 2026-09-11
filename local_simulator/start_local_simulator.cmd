@echo off
cd /d "%~dp0"
set "Q3PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%Q3PY%" (
  "%Q3PY%" simulator.py gui
) else (
  python simulator.py gui
)
if errorlevel 1 pause
