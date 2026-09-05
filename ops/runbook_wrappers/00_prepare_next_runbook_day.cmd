@echo off
setlocal

set "EXIT_CODE=1"

if not exist "%~dp0_machine.local.cmd" (
  echo Required machine environment file not found: "%~dp0_machine.local.cmd".
  goto :finish
)
call "%~dp0_machine.local.cmd"
set "LOCAL_EXIT_CODE=%ERRORLEVEL%"
if not "%LOCAL_EXIT_CODE%"=="0" (
  echo Failed to load machine environment. Exit code: %LOCAL_EXIT_CODE%
  set "EXIT_CODE=%LOCAL_EXIT_CODE%"
  goto :finish
)

if not exist "%~dp0_account.local.cmd" (
  echo Required account environment file not found: "%~dp0_account.local.cmd".
  goto :finish
)
call "%~dp0_account.local.cmd"
set "LOCAL_EXIT_CODE=%ERRORLEVEL%"
if not "%LOCAL_EXIT_CODE%"=="0" (
  echo Failed to load account environment. Exit code: %LOCAL_EXIT_CODE%
  set "EXIT_CODE=%LOCAL_EXIT_CODE%"
  goto :finish
)

if /I "%RUNBOOK_CHAINED_MODE%"=="1" set "PAUSE_ON_EXIT=0"

for %%V in (REPO_ROOT WORKSPACE CONDA_BAT CONDA_ENV_NAME PAUSE_ON_EXIT PYTHONUTF8 PYTHONIOENCODING ACCOUNT_ID ACCOUNT_MODE) do (
  if not defined %%V (
    echo Required variable %%V is not defined.
    set "EXIT_CODE=1"
    goto :finish
  )
)

if /I not "%ACCOUNT_MODE%"=="PAPER" (
  echo ACCOUNT_MODE must be PAPER.
  goto :finish
)

if not exist "%REPO_ROOT%" (
  echo Repository root not found: "%REPO_ROOT%".
  goto :finish
)
if not exist "%WORKSPACE%" (
  echo Workspace not found: "%WORKSPACE%".
  goto :finish
)
if not exist "%CONDA_BAT%" (
  echo Conda activation script not found: "%CONDA_BAT%".
  goto :finish
)
if not exist "%REPO_ROOT%\scripts\runbook_day_prep.py" (
  echo Runbook day prep script not found: "%REPO_ROOT%\scripts\runbook_day_prep.py".
  goto :finish
)

call "%CONDA_BAT%" activate "%CONDA_ENV_NAME%"
set "ACTIVATE_EXIT_CODE=%ERRORLEVEL%"
if not "%ACTIVATE_EXIT_CODE%"=="0" (
  echo Failed to activate Conda environment "%CONDA_ENV_NAME%". Exit code: %ACTIVATE_EXIT_CODE%
  set "EXIT_CODE=%ACTIVATE_EXIT_CODE%"
  goto :finish
)

if /I not "%CONDA_DEFAULT_ENV%"=="%CONDA_ENV_NAME%" (
  echo Unexpected Conda environment: "%CONDA_DEFAULT_ENV%". Expected "%CONDA_ENV_NAME%".
  goto :finish
)

if not exist "%CONDA_PREFIX%\python.exe" (
  echo Python executable not found in Conda environment: "%CONDA_PREFIX%\python.exe".
  goto :finish
)
set "PYTHON_EXE=%CONDA_PREFIX%\python.exe"

cd /d "%REPO_ROOT%"
if errorlevel 1 (
  echo Failed to change directory to "%REPO_ROOT%".
  goto :finish
)

"%PYTHON_EXE%" scripts\runbook_day_prep.py ^
  --workspace "%WORKSPACE%" ^
  --account-id "%ACCOUNT_ID%" ^
  --account-local "%~dp0_account.local.cmd" ^
  --runbook-day-local "%~dp0_runbook_day.local.cmd" ^
  --write-env-local ^
  --confirm-paper-test

set "EXIT_CODE=%ERRORLEVEL%"

:finish
echo.
echo ----------------------------------------
if "%EXIT_CODE%"=="0" (
  if not exist "%~dp0_runbook_day.local.cmd" (
    echo Expected runbook day environment file was not created: "%~dp0_runbook_day.local.cmd".
    set "EXIT_CODE=1"
  ) else (
    type "%~dp0_runbook_day.local.cmd"
    echo.
    echo Next action:
    echo Review ACCOUNT_ID, DATA_DATE, TRADE_DATE, and RUNBOOK_DAY_ID above.
    echo If they are correct, run 01_stage_a_plan_prep.cmd.
  )
)
if "%EXIT_CODE%"=="2" (
  echo Runbook day preparation was BLOCKED.
  echo The existing runbook-day environment was preserved.
  echo Do not run 01_stage_a_plan_prep.cmd until the blockers are resolved.
)
if not "%EXIT_CODE%"=="0" if not "%EXIT_CODE%"=="2" (
  echo Runbook day preparation failed.
  echo Inspect the error output before retrying.
  echo Do not run 01_stage_a_plan_prep.cmd.
)
echo Exit code: %EXIT_CODE%
if /I "%PAUSE_ON_EXIT%"=="1" pause
exit /b %EXIT_CODE%
