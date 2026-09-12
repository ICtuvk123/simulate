@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "Q3_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%Q3_PYTHON%" goto check_python
set "Q3_PYTHON="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "Q3_PYTHON=%%P"
if defined Q3_PYTHON goto check_python
for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "Q3_PYTHON=%%P"
if not defined Q3_PYTHON goto missing_python

:check_python
"%Q3_PYTHON%" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if errorlevel 1 goto missing_python
if /i "%~1"=="--gui-check" goto gui_check
if not "%~1"=="" goto command_line
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0time_push_20260912\test_helper.ps1" -PythonPath "%Q3_PYTHON%"
exit /b %errorlevel%

:gui_check
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0time_push_20260912\test_helper.ps1" -PythonPath "%Q3_PYTHON%" -SelfCheck
exit /b %errorlevel%

:command_line
"%Q3_PYTHON%" -u "%~dp0time_push_20260912\test_helper.py" %*
exit /b %errorlevel%

:missing_python
echo Python 3.10 or newer was not found. Please install Python and try again.
if "%~1"=="" pause
exit /b 1
