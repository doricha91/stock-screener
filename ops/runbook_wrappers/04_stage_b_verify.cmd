@echo off
call "%~dp0_env.cmd"
cd /d %REPO_ROOT%

python scripts\runbook_stage_b_verifier.py ^
  --workspace %WORKSPACE% ^
  --account-id %ACCOUNT_ID% ^
  --data-date %DATA_DATE% ^
  --trade-date %TRADE_DATE% ^
  --json

set EXIT_CODE=%ERRORLEVEL%
echo.
echo Exit code: %EXIT_CODE%
if not "%EXIT_CODE%"=="0" (
  echo Wrapper finished with non-zero exit code.
  exit /b %EXIT_CODE%
)
exit /b 0
