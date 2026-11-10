@echo off
title Local Speech Studio - Model Pre-Downloader
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\download_models.py
) else (
    python scripts\download_models.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Model download exited with code %ERRORLEVEL%.
)
pause

