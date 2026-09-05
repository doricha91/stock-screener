@echo off
setlocal
set "RUNBOOK_CHAINED_MODE=1"
call "%~dp0..\01_stage_a_plan_prep.cmd"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo Primary 01 PASS. Complete Manual Execution input only when required, then run 02_execution_to_review_prep.cmd.
) else (
  echo Primary 01 stopped. Primary 02 was NOT_RUN.
  echo Recovery: ..\01_stage_a_plan_prep.cmd
)
exit /b %EXIT_CODE%
