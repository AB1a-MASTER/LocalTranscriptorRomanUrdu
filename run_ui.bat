@echo off
title Local Speech-to-Text Studio
cd /d "%~dp0"

echo ===================================================
echo   Local Speech-to-Text Studio
echo   Urdu-English Mixed and Roman Urdu Pipeline
echo ===================================================
echo.

if exist ".venv\Scripts\python.exe" (
    echo Starting UI with local virtual environment...
    ".venv\Scripts\python.exe" scripts\ui.py
) else (
    echo Virtual environment not found at .venv. Trying system python...
    python scripts\ui.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with code %ERRORLEVEL%.
    pause
)

