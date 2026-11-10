@echo off
title Local Speech Studio - Stop Docker Container
cd /d "%~dp0"

echo Stopping Local Speech Studio container...
docker compose down
docker stop speech-studio-gpu >nul 2>&1
docker rm speech-studio-gpu >nul 2>&1

echo Studio container stopped successfully.
pause

