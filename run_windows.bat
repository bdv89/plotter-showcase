@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Simple Windows launcher that logs stdout/stderr to logs\app_debug.log
set LOGDIR=logs
set LOG=%LOGDIR%\app_debug.log
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo [run_windows.bat] Launching with Windows Python 3.13 ...>> "%LOG%"

REM Unbuffered mode (-u) and redirect both stdout and stderr to the log
py -3.13 -u launcher.py 1>> "%LOG%" 2>&1

if %ERRORLEVEL% NEQ 0 (
  echo [run_windows.bat] Process exited with errorlevel %ERRORLEVEL%>> "%LOG%"
)

echo [run_windows.bat] Done. Log: %LOG%
endlocal

