@echo off
title Local Speech Studio - Docker GPU Diagnostic Check
cd /d "%~dp0"

echo =================================================================
echo   TESTING GPU ACCELERATION IN DOCKER
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

docker run --rm --gpus all local-speech-studio:gpu verify

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] GPU test failed or image 'local-speech-studio:gpu' not found.
    echo Run 'docker_build.bat' first to build the image.
)

echo.
pause

