@echo off
title Local Speech Studio - Start Web-Accessible UI
cd /d "%~dp0"

echo =================================================================
echo   STARTING LOCAL SPEECH STUDIO (DOCKER GPU CONTAINER)
echo =================================================================
echo.

if not exist "output" mkdir output
if not exist "cache\huggingface" mkdir cache\huggingface

docker compose up -d studio

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to start container via docker compose.
    echo Trying manual docker run fallback...
    docker run -d --name speech-studio-gpu --gpus all -p 6080:6080 ^
        -v "%cd%\input:/app/input" ^
        -v "%cd%\output:/app/output" ^
        -v "%cd%\cache\huggingface:/root/.cache/huggingface" ^
        local-speech-studio:gpu studio
)

echo.
echo =================================================================
echo   STUDIO IS RUNNING!
echo   Opening: http://localhost:6080/vnc.html in your default browser...
echo =================================================================
echo To stop the studio, run: docker_stop_studio.bat
echo =================================================================
echo.

timeout /t 2 >nul
start http://localhost:6080/vnc.html

pause

