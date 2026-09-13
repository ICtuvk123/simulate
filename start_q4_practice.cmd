@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 "%~dp0start_practice.py"
goto done
:use_python
where python >nul 2>nul
if errorlevel 1 goto missing_python
python "%~dp0start_practice.py"
goto done
:missing_python
echo Python 3.10 or newer is required. Install Python and reopen this file.
:done
echo.
pause
