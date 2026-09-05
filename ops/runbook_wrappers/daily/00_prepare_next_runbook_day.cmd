@echo off
setlocal
set "RUNBOOK_CHAINED_MODE=1"
call "%~dp0..\00_prepare_next_runbook_day.cmd"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo Primary 00 PASS. Review the frozen Runbook dates, then run 01_stage_a_plan_prep.cmd.
) else (
  echo Primary 00 stopped. Stage A was NOT_RUN.
  echo Recovery: ..\00_prepare_next_runbook_day.cmd
)
exit /b %EXIT_CODE%
