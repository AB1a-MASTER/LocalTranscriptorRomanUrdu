@echo off
setlocal enabledelayedexpansion
title Local Speech Studio - 1-Click Docker GPU Launcher
cd /d "%~dp0"

echo =================================================================
echo   LOCAL SPEECH STUDIO - 1-CLICK DOCKER GPU LAUNCHER
echo =================================================================
echo.

:: 1. Add standard Docker path if present
if exist "C:\Program Files\Docker\Docker\resources\bin\docker.exe" (
    set "PATH=C:\Program Files\Docker\Docker\resources\bin;%PATH%"
)

:: 2. Check if Docker is installed and running
where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Docker is not installed. Launching automated installer...
    call "%~dp0install_or_start_docker.bat"
    if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
)

:: Check if Docker daemon is responding
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Docker daemon is not active. Initializing engine...
    call "%~dp0install_or_start_docker.bat"
    if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
)

:: 3. Check if Docker image is built
docker image inspect local-speech-studio:gpu >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo =================================================================
    echo [STEP 1/2] Building 'local-speech-studio:gpu' container image...
    echo (First build takes 3-5 mins to download CUDA 12 and dependencies)
    echo =================================================================
    echo.
    docker build -t local-speech-studio:gpu .
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to build Docker image.
        pause
        exit /b 1
    )
) else (
    echo [OK] Container image 'local-speech-studio:gpu' is ready.
)

:: 4. Ensure mount directories exist
if not exist "input" mkdir input
if not exist "output" mkdir output
if not exist "cache\huggingface" mkdir cache\huggingface

:: 5. Start Studio Container
echo.
echo =================================================================
echo [STEP 2/2] Starting Studio Container with GPU Acceleration...
echo =================================================================
echo.

docker compose up -d studio >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    docker run -d --name speech-studio-gpu --gpus all -p 6080:6080 ^
        -v "%cd%\input:/app/input" ^
        -v "%cd%\output:/app/output" ^
        -v "%cd%\cache\huggingface:/root/.cache/huggingface" ^
        local-speech-studio:gpu studio
)

echo.
echo =================================================================
echo   >>> SUCCESS! LOCAL SPEECH STUDIO IS RUNNING <<<
echo   Opening Studio in your web browser: http://localhost:6080/vnc.html
echo =================================================================
echo To stop the studio later, double-click: docker_stop_studio.bat
echo =================================================================
echo.

timeout /t 2 >nul
start http://localhost:6080/vnc.html

pause

