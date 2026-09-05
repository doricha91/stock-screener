@echo off
setlocal
set "RUNBOOK_CHAINED_MODE=1"
call "%~dp0..\_env.cmd"
set "ENV_EXIT_CODE=%ERRORLEVEL%"
if not "%ENV_EXIT_CODE%"=="0" exit /b %ENV_EXIT_CODE%
cd /d "%REPO_ROOT%"
if errorlevel 1 exit /b 1
"%PYTHON_EXE%" scripts\runbook_primary_flow.py close-day ^
  --workspace "%WORKSPACE%" ^
  --account-id "%ACCOUNT_ID%" ^
  --data-date "%DATA_DATE%" ^
  --trade-date "%TRADE_DATE%" ^
  --confirm-paper-test
exit /b %ERRORLEVEL%
