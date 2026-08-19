@echo off
REM ============================================================================
REM  ISMO HR Assistant - (re)build the document index
REM
REM  The vector store is derived data and is not kept in version control, so a
REM  fresh deployment starts with nothing to answer policy questions from. This
REM  rebuilds it from the documents in uploads\.
REM
REM    train_documents.bat            index anything not indexed yet
REM    train_documents.bat --reset    drop the collection and rebuild it
REM                                   (needed after changing the embedding model)
REM    train_documents.bat status     show what is currently indexed
REM ============================================================================

setlocal
cd /d "%~dp0"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if not exist "venv\Scripts\python.exe" (
    echo ERROR: no virtual environment. Run run_server.bat once to create it.
    pause
    exit /b 1
)

if /i "%~1"=="status" (
    "venv\Scripts\python.exe" -m app.cli status
    pause
    exit /b 0
)

echo Indexing documents from uploads\ ...
"venv\Scripts\python.exe" -m app.cli reindex %*

if errorlevel 1 (
    echo.
    echo Indexing reported a problem. Check that Ollama is running and that
    echo "ollama pull nomic-embed-text" has been done on this machine.
)

echo.
"venv\Scripts\python.exe" -m app.cli status

echo.
echo ===========================================================================
echo  If the assistant service is already running, restart it now (run_server.bat).
echo  Documents trained here are not searchable by a process that started before
echo  them. Training through the chat widget does not need a restart.
echo ===========================================================================
pause
endlocal
