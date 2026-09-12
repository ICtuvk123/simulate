@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PRACTICE_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%PRACTICE_PY%" goto bundled
where py >nul 2>nul
if not errorlevel 1 goto pylauncher
where python >nul 2>nul
if not errorlevel 1 goto pythonpath
echo Python 3.10+ is required. Install Python and enable Add Python to PATH.
goto finish
:bundled
"%PRACTICE_PY%" "%~dp0code\manual_official_practice.py" %*
goto finish
:pylauncher
py -3 "%~dp0code\manual_official_practice.py" %*
goto finish
:pythonpath
python "%~dp0code\manual_official_practice.py" %*
:finish
echo.
pause
