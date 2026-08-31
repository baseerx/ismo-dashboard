@echo off
setlocal EnableExtensions

REM ==========================================
REM Configuration
REM ==========================================
set "PROJECT_PATH=C:\Program Files\Apache24\htdocs\BioMetric-Django-Backend"
set "VENV_PATH=%PROJECT_PATH%\venv"
set "PYTHON_EXE=%VENV_PATH%\Scripts\python.exe"
set "WAITRESS_EXE=%VENV_PATH%\Scripts\waitress-serve.exe"
set "LOG_PATH=%PROJECT_PATH%\waitress.log"
set "PORT=9002"

echo.
echo ==========================================
echo   Django + Waitress Server
echo ==========================================
echo Project : %PROJECT_PATH%
echo Port    : %PORT%
echo Log     : %LOG_PATH%
echo ==========================================
echo.

REM ==========================================
REM Validate project
REM ==========================================
if not exist "%PROJECT_PATH%" (
    echo ERROR: Project path does not exist:
    echo %PROJECT_PATH%
    pause
    exit /b 1
)

REM ==========================================
REM Validate Python
REM ==========================================
if not exist "%PYTHON_EXE%" (
    echo ERROR: Virtual environment Python not found:
    echo %PYTHON_EXE%
    pause
    exit /b 1
)

REM ==========================================
REM Validate Waitress
REM ==========================================
if not exist "%WAITRESS_EXE%" (
    echo ERROR: Waitress is not installed in the virtual environment.
    echo.
    echo Install it using:
    echo "%PYTHON_EXE%" -m pip install waitress
    pause
    exit /b 1
)

REM ==========================================
REM Change to project directory
REM ==========================================
cd /d "%PROJECT_PATH%"

set "PYTHONPATH=%PROJECT_PATH%"
set "DJANGO_SETTINGS_MODULE=hris.settings"

REM ==========================================
REM Kill existing process using port
REM ==========================================
echo Checking port %PORT%...

for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%PORT%" ^| findstr LISTENING') do (
    echo Stopping existing process PID %%P
    taskkill /F /PID %%P >nul 2>&1
)

timeout /t 2 /nobreak >nul

REM ==========================================
REM Start Waitress
REM ==========================================
echo.
echo Starting Waitress...
echo.

echo ========================================== > "%LOG_PATH%"
echo Waitress started: %date% %time% >> "%LOG_PATH%"
echo Project: %PROJECT_PATH% >> "%LOG_PATH%"
echo Port: %PORT% >> "%LOG_PATH%"
echo ========================================== >> "%LOG_PATH%"

REM Start Waitress in background and redirect ALL output
start "" /B "%PYTHON_EXE%" -m waitress ^
    --host=0.0.0.0 ^
    --port=%PORT% ^
    --threads=8 ^
    --call ^
    hris.wsgi:application >> "%LOG_PATH%" 2>&1

timeout /t 5 /nobreak >nul

REM ==========================================
REM Verify port
REM ==========================================
netstat -ano | findstr ":%PORT%" | findstr LISTENING >nul

if %errorlevel%==0 (
    echo.
    echo ==========================================
    echo SUCCESS
    echo ==========================================
    echo Waitress is running on port %PORT%.
    echo.
    echo Log file:
    echo %LOG_PATH%
    echo.
    echo Test:
    echo http://localhost:%PORT%
    echo ==========================================
) else (
    echo.
    echo ==========================================
    echo ERROR
    echo ==========================================
    echo Waitress failed to start.
    echo.
    echo Check the log:
    echo %LOG_PATH%
    echo.
    echo Last log entries:
    echo ------------------------------------------
    powershell -NoProfile -Command "Get-Content '%LOG_PATH%' -Tail 30"
    echo ------------------------------------------
)

echo.
exit /b 0