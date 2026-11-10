@echo off
title Local Speech Studio - Pre-Download Models (Docker)
cd /d "%~dp0"

echo =================================================================
echo   PRE-DOWNLOADING WHISPER MODELS (DOCKER)
echo =================================================================
echo.

if not exist "cache\huggingface" mkdir cache\huggingface

docker run --rm -it --gpus all ^
    -v "%cd%\cache\huggingface:/root/.cache/huggingface" ^
    local-speech-studio:gpu download

pause

