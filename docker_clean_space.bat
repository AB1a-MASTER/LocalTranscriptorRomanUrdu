@echo off
title Local Speech Studio - Docker Disk Space Cleaner
cd /d "%~dp0"

echo =================================================================
echo   LOCAL SPEECH STUDIO - DOCKER DISK CLEANUP UTILITY
echo =================================================================
echo.
echo This script will:
echo   1. Stop any running studio containers
echo   2. Remove the previous 24 GB container image
echo   3. Purge cached intermediate build layers
echo.
set /p CONFIRM="Proceed with cleanup to reclaim disk space? [Y/N] (default=Y): "
if /i "%CONFIRM%"=="N" exit /b 0

echo.
echo [1/3] Stopping containers...
docker compose down >nul 2>&1
docker stop speech-studio-gpu >nul 2>&1
docker rm speech-studio-gpu >nul 2>&1

echo.
echo [2/3] Removing old 'local-speech-studio:gpu' image...
docker rmi local-speech-studio:gpu >nul 2>&1

echo.
echo [3/3] Purging Docker build cache...
docker builder prune -f

echo.
echo =================================================================
echo   CLEANUP FINISHED!
echo =================================================================
echo You can now rebuild the new ultra-lean (~2.5 GB) image by running:
echo   docker_build.bat   or   1_CLICK_RUN_DOCKER_GPU.bat
echo =================================================================
echo.
pause

