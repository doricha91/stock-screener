@echo off

if not exist "%~dp0_machine.local.cmd" (
  echo Required machine environment file not found: "%~dp0_machine.local.cmd".
  exit /b 1
)
call "%~dp0_machine.local.cmd"
set "LOCAL_EXIT_CODE=%ERRORLEVEL%"
if not "%LOCAL_EXIT_CODE%"=="0" (
  echo Failed to load machine environment. Exit code: %LOCAL_EXIT_CODE%
  exit /b %LOCAL_EXIT_CODE%
)

if not exist "%~dp0_account.local.cmd" (
  echo Required account environment file not found: "%~dp0_account.local.cmd".
  exit /b 1
)
call "%~dp0_account.local.cmd"
set "LOCAL_EXIT_CODE=%ERRORLEVEL%"
if not "%LOCAL_EXIT_CODE%"=="0" (
  echo Failed to load account environment. Exit code: %LOCAL_EXIT_CODE%
  exit /b %LOCAL_EXIT_CODE%
)

if not exist "%~dp0_runbook_day.local.cmd" (
  echo Required runbook day environment file not found: "%~dp0_runbook_day.local.cmd".
  exit /b 1
)
call "%~dp0_runbook_day.local.cmd"
set "LOCAL_EXIT_CODE=%ERRORLEVEL%"
if not "%LOCAL_EXIT_CODE%"=="0" (
  echo Failed to load runbook day environment. Exit code: %LOCAL_EXIT_CODE%
  exit /b %LOCAL_EXIT_CODE%
)

for %%V in (REPO_ROOT WORKSPACE CONDA_BAT CONDA_ENV_NAME PAUSE_ON_EXIT PYTHONUTF8 PYTHONIOENCODING ACCOUNT_ID ACCOUNT_MODE DATA_DATE TRADE_DATE RUNBOOK_DAY_ID) do (
  if not defined %%V (
    echo Required environment variable %%V is not defined.
    exit /b 1
  )
)

if /I not "%ACCOUNT_MODE%"=="PAPER" (
  echo ACCOUNT_MODE must be PAPER.
  exit /b 1
)

set "EXPECTED_RUNBOOK_DAY_ID=%ACCOUNT_ID%_%DATA_DATE%_%TRADE_DATE%"
if not "%RUNBOOK_DAY_ID%"=="%EXPECTED_RUNBOOK_DAY_ID%" (
  echo RUNBOOK_DAY_ID does not match ACCOUNT_ID, DATA_DATE, and TRADE_DATE.
  exit /b 1
)

if not exist "%REPO_ROOT%" (
  echo Repository root not found: "%REPO_ROOT%".
  exit /b 1
)
if not exist "%WORKSPACE%" (
  echo Workspace not found: "%WORKSPACE%".
  exit /b 1
)
if not exist "%CONDA_BAT%" (
  echo Conda activation script not found: "%CONDA_BAT%".
  exit /b 1
)

call "%CONDA_BAT%" activate "%CONDA_ENV_NAME%"
set "ACTIVATE_EXIT_CODE=%ERRORLEVEL%"
if not "%ACTIVATE_EXIT_CODE%"=="0" (
  echo Failed to activate Conda environment "%CONDA_ENV_NAME%". Exit code: %ACTIVATE_EXIT_CODE%
  exit /b %ACTIVATE_EXIT_CODE%
)

if /I not "%CONDA_DEFAULT_ENV%"=="%CONDA_ENV_NAME%" (
  echo Unexpected Conda environment: "%CONDA_DEFAULT_ENV%". Expected "%CONDA_ENV_NAME%".
  exit /b 1
)

if not exist "%CONDA_PREFIX%\python.exe" (
  echo Python executable not found in Conda environment: "%CONDA_PREFIX%\python.exe".
  exit /b 1
)

set "PYTHON_EXE=%CONDA_PREFIX%\python.exe"
exit /b 0
