@echo off
setlocal

call "%~dp0_env.cmd"
set "ENV_EXIT_CODE=%ERRORLEVEL%"
if not "%ENV_EXIT_CODE%"=="0" (
  echo Failed to initialize wrapper environment.
  if /I "%PAUSE_ON_EXIT%"=="1" pause
  exit /b %ENV_EXIT_CODE%
)

for %%V in (REPO_ROOT WORKSPACE ACCOUNT_ID DATA_DATE TRADE_DATE PYTHON_EXE) do (
  if not defined %%V (
    echo Required variable %%V is not defined.
    if /I "%PAUSE_ON_EXIT%"=="1" pause
    exit /b 1
  )
)

if not exist "%PYTHON_EXE%" (
  echo Python executable not found: "%PYTHON_EXE%".
  if /I "%PAUSE_ON_EXIT%"=="1" pause
  exit /b 1
)

cd /d "%REPO_ROOT%"
if errorlevel 1 (
  echo Failed to change directory to "%REPO_ROOT%".
  if /I "%PAUSE_ON_EXIT%"=="1" pause
  exit /b 1
)

"%PYTHON_EXE%" scripts\runbook_stage_runner.py stage-d-preview ^
  --workspace "%WORKSPACE%" ^
  --account-id "%ACCOUNT_ID%" ^
  --data-date "%DATA_DATE%" ^
  --trade-date "%TRADE_DATE%" ^
  --confirm-paper-test

set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo Exit code: %EXIT_CODE%
if /I "%PAUSE_ON_EXIT%"=="1" pause
exit /b %EXIT_CODE%
