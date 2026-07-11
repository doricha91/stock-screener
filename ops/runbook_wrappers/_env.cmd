@echo off
set "REPO_ROOT=D:\python\StockScreener"
set "WORKSPACE=D:\n8n\workspace\stock_screener_ops"
set "ACCOUNT_ID=paper_pilot_202606"
set "DATA_DATE=2026-07-01"
set "TRADE_DATE=2026-07-02"
set "PAUSE_ON_EXIT=0"
set "CONDA_BAT=C:\Users\inocha\anaconda3\condabin\conda.bat"

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
