@echo off
setlocal DisableDelayedExpansion
"%SystemRoot%\System32\chcp.com" 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
set "Q4_LAUNCH_OPTION="
if "%~1"=="--check-only" set "Q4_LAUNCH_OPTION=--check-only"

rem Discover an existing interpreter even when Python is absent from PATH.
if exist "%~dp0runtime\python.exe" (
  "%~dp0runtime\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
  if not errorlevel 1 (
    "%~dp0runtime\python.exe" -X utf8 "%~dp0start_practice.py" %Q4_LAUNCH_OPTION%
    goto done
  )
)
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
  if exist "%%~fD\python.exe" (
    "%%~fD\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
    if not errorlevel 1 (
      "%%~fD\python.exe" -X utf8 "%~dp0start_practice.py" %Q4_LAUNCH_OPTION%
      goto done
    )
  )
)
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
  "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
  if not errorlevel 1 (
    "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -X utf8 "%~dp0start_practice.py" %Q4_LAUNCH_OPTION%
    goto done
  )
)
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 (
  py -3 -X utf8 "%~dp0start_practice.py" %Q4_LAUNCH_OPTION%
  goto done
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 (
  python -X utf8 "%~dp0start_practice.py" %Q4_LAUNCH_OPTION%
  goto done
)
:missing_python
echo No usable Python 3.10 or newer was found in PATH or the usual installation folders.
echo Install Python, or place a portable Python distribution in this folder's runtime directory.
set "Q4_EXIT_CODE=2"
goto finish
:done
set "Q4_EXIT_CODE=%ERRORLEVEL%"
:finish
if "%~1"=="--check-only" exit /b %Q4_EXIT_CODE%
echo.
pause
exit /b %Q4_EXIT_CODE%
