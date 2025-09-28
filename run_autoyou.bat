@echo off
setlocal enabledelayedexpansion

REM Change to the directory of this script
cd /d "%~dp0"

echo ===============================================
echo   AutoYou AI Agent - One-Click Windows Runner
echo ===============================================

echo.
echo [1/5] Checking for Python...
where python >nul 2>&1
if %ERRORLEVEL%==0 (
  set "PYTHON_EXE=python"
) else (
  where py >nul 2>&1
  if %ERRORLEVEL%==0 (
    set "PYTHON_EXE=py -3"
  ) else (
    echo.
    echo ERROR: Python 3.9+ is required but was not found on PATH.
    echo Please install Python from https://www.python.org/downloads/ and try again.
    echo.
    pause
    exit /b 1
  )
)

echo.
echo [2/5] Creating virtual environment (.venv) if needed...
if not exist ".venv\Scripts\python.exe" (
  %PYTHON_EXE% -m venv .venv
  if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Failed to create virtual environment.
    echo.
    pause
    exit /b 1
  )
) else (
  echo Virtual environment already exists.
)

echo.
echo [3/5] Activating virtual environment...
call ".venv\Scripts\activate.bat"
if %ERRORLEVEL% neq 0 (
  echo.
  echo ERROR: Failed to activate virtual environment.
  echo.
  pause
  exit /b 1
)

echo.
echo [4/5] Upgrading pip and installing dependencies...
python -m pip install --upgrade pip
if %ERRORLEVEL% neq 0 (
  echo.
  echo WARNING: Failed to upgrade pip. Continuing...
)

pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
  echo.
  echo ERROR: Failed to install dependencies from requirements.txt
  echo.
  pause
  exit /b 1
)

echo.
echo [5/5] Starting AutoYou AI Agent server...
echo You can stop the server at any time with Ctrl+C.
echo.

python server.py --host 0.0.0.0 --port 8001
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
  echo.
  echo Server exited with error code %EXITCODE%.
  echo.
  pause
)

endlocal