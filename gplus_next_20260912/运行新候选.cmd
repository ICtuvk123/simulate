@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "NEXT_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%NEXT_PYTHON%" goto bundled
where py >nul 2>nul
if not errorlevel 1 goto launcher
where python >nul 2>nul
if not errorlevel 1 goto pythonpath
echo Python 3.10 or newer is required.
goto finish
:bundled
"%NEXT_PYTHON%" "%~dp0run_candidate.py" --seed 22001 %*
goto finish
:launcher
py -3 "%~dp0run_candidate.py" --seed 22001 %*
goto finish
:pythonpath
python "%~dp0run_candidate.py" --seed 22001 %*
:finish
echo.
pause
