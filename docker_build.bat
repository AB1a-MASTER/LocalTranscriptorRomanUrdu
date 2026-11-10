@echo off
title Local Speech Studio - Docker GPU Build
cd /d "%~dp0"

echo =================================================================
echo   BUILDING LOCAL SPEECH STUDIO DOCKER IMAGE (CUDA 12)
echo =================================================================
echo.

docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker is not installed or not in PATH.
    echo Please install Docker Desktop with WSL2 and NVIDIA Container Toolkit.
    pause
    exit /b 1
)

echo Building image 'local-speech-studio:gpu'...
echo (This may take several minutes on first build to download CUDA base layers)
echo.

docker build -t local-speech-studio:gpu .

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Docker build failed with code %ERRORLEVEL%.
    pause
    exit /b 1
)

echo.
echo =================================================================
echo   DOCKER IMAGE SUCCESSFULLY BUILT!
echo =================================================================
echo To verify GPU recognition, run:     docker_test_gpu.bat
echo To test Whisper Large-v3, run:      docker_transcribe_test.bat
echo To start the web-accessible UI, run: docker_run_studio.bat
echo =================================================================
echo.
pause

