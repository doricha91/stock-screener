@echo off
set "REPO_ROOT=D:\python\StockScreener"
set "WORKSPACE=D:\n8n\workspace\stock_screener_ops"
set "PAUSE_ON_EXIT=0"
set "CONDA_BAT=C:\Users\inocha\anaconda3\condabin\conda.bat"

if not exist "%~dp0_env.local.cmd" (
  echo Required local environment file not found: "%~dp0_env.local.cmd".
  exit /b 1
)

call "%~dp0_env.local.cmd"
set "LOCAL_ENV_EXIT_CODE=%ERRORLEVEL%"
if not "%LOCAL_ENV_EXIT_CODE%"=="0" (
  echo Failed to load local runbook environment. Exit code: %LOCAL_ENV_EXIT_CODE%
  exit /b %LOCAL_ENV_EXIT_CODE%
)

for %%V in (ACCOUNT_ID DATA_DATE TRADE_DATE RUNBOOK_DAY_ID) do (
  if not defined %%V (
    echo Required local variable %%V is not defined.
    exit /b 1
  )
)

set "EXPECTED_RUNBOOK_DAY_ID=%ACCOUNT_ID%_%DATA_DATE%_%TRADE_DATE%"
if not "%RUNBOOK_DAY_ID%"=="%EXPECTED_RUNBOOK_DAY_ID%" (
  echo RUNBOOK_DAY_ID does not match ACCOUNT_ID, DATA_DATE, and TRADE_DATE.
  exit /b 1
)

if not exist "%CONDA_BAT%" (
  echo Conda activation script not found: "%CONDA_BAT%".
  exit /b 1
)

call "%CONDA_BAT%" activate HANTU311_64
set "ACTIVATE_EXIT_CODE=%ERRORLEVEL%"
if not "%ACTIVATE_EXIT_CODE%"=="0" (
  echo Failed to activate Conda environment HANTU311_64. Exit code: %ACTIVATE_EXIT_CODE%
  exit /b %ACTIVATE_EXIT_CODE%
)

if /I not "%CONDA_DEFAULT_ENV%"=="HANTU311_64" (
  echo Unexpected Conda environment: "%CONDA_DEFAULT_ENV%". Expected "HANTU311_64".
  exit /b 1
)

if not exist "%CONDA_PREFIX%\python.exe" (
  echo Python executable not found in Conda environment: "%CONDA_PREFIX%\python.exe".
  exit /b 1
)

set "PYTHON_EXE=%CONDA_PREFIX%\python.exe"
exit /b 0
