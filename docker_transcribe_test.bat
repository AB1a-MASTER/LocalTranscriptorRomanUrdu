@echo off
title Local Speech Studio - Whisper Large-v3 GPU Transcription Test
cd /d "%~dp0"

echo =================================================================
echo   TESTING WHISPER LARGE-V3 TRANSCRIPTION ON NVIDIA GPU (DOCKER)
echo =================================================================
echo.

if exist "C:\Program Files\Docker\Docker\resources\bin\docker.exe" (
    set "PATH=C:\Program Files\Docker\Docker\resources\bin;%PATH%"
)

where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Docker not found. Launching automated installer...
    call "%~dp0install_or_start_docker.bat"
)

docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Docker daemon not running. Starting Docker engine...
    call "%~dp0install_or_start_docker.bat"
)

if not exist "input\test.wav" (
    echo [WARNING] 'input\test.wav' not found.
    echo Please place your test audio file in the 'input\' folder.
)

if not exist "output" mkdir output
if not exist "cache\huggingface" mkdir cache\huggingface

echo Starting transcription test with Whisper Large-v3 Full (1550M)...
echo Outputs will be saved to: %cd%\output\
echo.

docker run --rm --gpus all ^
    -v "%cd%\input:/app/input" ^
    -v "%cd%\output:/app/output" ^
    -v "%cd%\cache\huggingface:/root/.cache/huggingface" ^
    local-speech-studio:gpu test

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Transcription test failed with code %ERRORLEVEL%.
) else (
    echo.
    echo =================================================================
    echo   TRANSCRIPTION COMPLETED SUCCESSFULLY!
    echo   Check output folder: %cd%\output\
    echo =================================================================
)

echo.
pause

