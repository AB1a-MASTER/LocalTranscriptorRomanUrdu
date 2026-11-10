@echo off
title Local Speech Studio 2.0 - Modern Web Edition
cd /d "%~dp0"

echo =================================================================
echo   STARTING LOCAL SPEECH STUDIO 2.0 (MODERN DESKTOP STUDIO)
echo =================================================================
echo   No clipping - Fluid 60fps - Real Waveform - Karaoke Highlight
echo   Opening interface in your browser: http://127.0.0.1:7860
echo.

.venv\Scripts\python.exe scripts\studio_web.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Studio exited with code %ERRORLEVEL%.
    pause
)

