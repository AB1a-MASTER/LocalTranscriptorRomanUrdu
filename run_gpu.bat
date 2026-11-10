@echo off
title Local Speech Studio - GPU Accelerated
cd /d "%~dp0"

echo =================================================================
echo   Local Speech Studio (GPU Accelerated)
echo   Urdu-English Mixed & Roman Urdu Transcription
echo =================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    echo Starting Studio with GPU-enabled environment...
    ".venv\Scripts\python.exe" scripts\ui.py
) else (
    echo [WARNING] Local virtual environment (.venv) not found.
    echo Please run 'setup_gpu.bat' first to install GPU dependencies.
    echo.
    echo Trying system python as fallback...
    python scripts\ui.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with code %ERRORLEVEL%.
    pause
)

