@echo off
setlocal
set "TASK_PYTHON=C:\Users\12831\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
"%TASK_PYTHON%" "%~dp0run_candidate.py" --seed 13001 %*
pause
