@echo off
REM ============================================================================
REM  ISMO HR Assistant - start the chatbot API
REM
REM  Double-click this file, or run it from a scheduled task / service wrapper.
REM  It creates the virtual environment and installs dependencies on first run,
REM  so a fresh machine needs nothing but Python 3.12 and the SQL Server ODBC
REM  driver.
REM
REM  Settings come from .env (copy .env.example to .env). HOST and PORT below
REM  can be overridden by setting them before calling this script.
REM ============================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

if "%HOST%"=="" set HOST=0.0.0.0
if "%PORT%"=="" set PORT=8000
if "%WORKERS%"=="" set WORKERS=1

REM Log files and the console both carry policy text and employee names, which
REM are not all ASCII.
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo.
echo === ISMO HR Assistant =====================================================

if not exist "venv\Scripts\python.exe" (
    echo Creating the virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo.
        echo ERROR: could not create the virtual environment. Is Python 3.12 on PATH?
        pause
        exit /b 1
    )
    echo Installing dependencies...
    "venv\Scripts\python.exe" -m pip install --upgrade pip
    "venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: dependency installation failed.
        pause
        exit /b 1
    )
)

if not exist ".env" (
    echo.
    echo NOTE: no .env file found - falling back to the built-in defaults.
    echo       Copy .env.example to .env and set DJANGO_SECRET_KEY to the value
    echo       in backend\hris\settings.py, or every login token will be rejected.
    echo.
)

REM Ollama serves both the chat model and the embedding model. Without it the
REM service starts but every policy answer fails, so say so plainly up front.
curl -s -o NUL -m 3 http://localhost:11434/api/tags
if errorlevel 1 (
    echo WARNING: Ollama does not answer on http://localhost:11434
    echo          Start it with "ollama serve", and make sure these are pulled:
    echo            ollama pull mistral
    echo            ollama pull nomic-embed-text
    echo.
)

echo Starting on http://%HOST%:%PORT%  (Ctrl+C to stop)
echo ===========================================================================
echo.

"venv\Scripts\python.exe" -m uvicorn app.main:app --host %HOST% --port %PORT% --workers %WORKERS%

if errorlevel 1 (
    echo.
    echo The server exited with an error. The most common causes are:
    echo   - port %PORT% already in use
    echo   - SQL Server unreachable (check DB_HOST / DB_NAME in .env)
    echo   - ODBC Driver 17 for SQL Server not installed
    pause
)

endlocal
