@echo off
REM ============================================================
REM  ResilientRoute - One-click startup script (Windows)
REM ============================================================
REM  Usage: scripts\start.bat [--offline] [--no-llm]
REM
REM  This script:
REM  1. Checks Python availability
REM  2. Creates virtual environment if needed
REM  3. Installs dependencies
REM  4. Validates data files
REM  5. Starts the FastAPI backend server
REM ============================================================

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

REM Remove trailing backslash
if "%PROJECT_ROOT:~-1%"=="\" set PROJECT_ROOT=%PROJECT_ROOT:~0,-1%

set VENV_DIR=%PROJECT_ROOT%\.venv
set PORT=8000
set OFFLINE_FLAG=

REM Parse arguments
:parse_args
if "%1"=="--offline" (
    set OFFLINE_FLAG=OFFLINE_MODE=true
    echo [INFO] Offline mode enabled - no external API calls
    shift
    goto parse_args
)
if "%1"=="--no-llm" (
    set LLM_ENABLED=false
    echo [INFO] LLM disabled - using deterministic fallback
    shift
    goto parse_args
)

echo ============================================================
echo   ResilientRoute - Starting up...
echo ============================================================

REM --- Step 1: Check Python ---
echo [1/5] Checking Python...
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.11+.
    exit /b 1
)
for /f "delims=" %%i in ('python --version 2^>^&1') do set PY_VERSION=%%i
echo   Found: %PY_VERSION%

REM --- Step 2: Create venv if needed ---
echo.
echo [2/5] Setting up virtual environment...
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo   Creating virtual environment...
    python -m venv "%VENV_DIR%"
)
set PYTHON_BIN=%VENV_DIR%\Scripts\python.exe
set PIP=%VENV_DIR%\Scripts\pip.exe

REM --- Step 3: Install dependencies ---
echo.
echo [3/5] Installing dependencies...
"%PIP%" install --quiet --upgrade pip
"%PIP%" install --quiet -r "%PROJECT_ROOT%\backend\requirements.txt"
echo   Dependencies installed.

REM --- Step 4: Validate data ---
echo.
echo [4/5] Validating data files...
"%PYTHON_BIN%" "%PROJECT_ROOT%\scripts\validate_data.py"
if %ERRORLEVEL% neq 0 (
    echo [WARN] Data validation found issues. Continuing anyway.
)

REM --- Step 5: Start server ---
echo.
echo [5/5] Starting FastAPI server...
echo   Port: %PORT%
echo   Docs: http://localhost:%PORT%/docs
echo   Health: http://localhost:%PORT%/api/health
echo.
echo   Press Ctrl+C to stop.
echo ============================================================

cd /d "%PROJECT_ROOT%"
"%PYTHON_BIN%" -m uvicorn backend.app.main:app --host 0.0.0.0 --port %PORT% --reload
