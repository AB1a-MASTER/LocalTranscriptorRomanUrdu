@echo off
setlocal enabledelayedexpansion
title Docker Automated Installer & Engine Launcher
cd /d "%~dp0"

echo =================================================================
echo   LOCAL SPEECH STUDIO - ONE-CLICK DOCKER SETUP
echo =================================================================
echo.

:: 1. Check for Administrator Privileges (Auto-Elevate if needed)
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Administrator rights required for Docker / WSL setup.
    echo Requesting elevation...
    powershell -Command "Start-Process cmd.exe -ArgumentList '/c', '\"%~f0\"' -Verb RunAs"
    exit /b
)

:: 2. Ensure Docker binary path is in current session
if exist "C:\Program Files\Docker\Docker\resources\bin\docker.exe" (
    set "PATH=C:\Program Files\Docker\Docker\resources\bin;%PATH%"
)

:: 3. Check if Docker is installed
where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    goto :INSTALL_DOCKER
) else (
    echo [OK] Docker installation detected.
    goto :START_DOCKER_ENGINE
)

:INSTALL_DOCKER
echo [STEP 1/3] Docker is not installed on this system.
echo Preparing automated installation of Docker Desktop...
echo.

:: Verify / Update WSL2 subsystem
echo Checking WSL2 subsystem status...
wsl --status >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Enabling WSL subsystem for Windows...
    wsl --install --no-distribution
) else (
    echo [OK] WSL is present. Checking updates...
    wsl --update >nul 2>&1
)

:: Download Docker Desktop Installer
set "INSTALLER_PATH=%TEMP%\DockerDesktopInstaller.exe"
echo.
echo [STEP 2/3] Downloading Docker Desktop Installer from official servers...
echo URL: https://desktop.docker.com/win/main/amd64/Docker Desktop Installer.exe
echo Saving to: %INSTALLER_PATH%
echo.

curl.exe -L "https://desktop.docker.com/win/main/amd64/Docker%%20Desktop%%20Installer.exe" -o "%INSTALLER_PATH%"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [WARNING] curl failed. Attempting PowerShell download fallback...
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('https://desktop.docker.com/win/main/amd64/Docker%%20Desktop%%20Installer.exe', '$env:TEMP\DockerDesktopInstaller.exe')"
)

if not exist "%INSTALLER_PATH%" (
    echo [ERROR] Failed to download Docker Desktop installer.
    echo Please verify internet connectivity.
    pause
    exit /b 1
)

:: Install Docker Desktop quietly with license accepted
echo.
echo [STEP 3/3] Installing Docker Desktop (unattended)...
echo Please wait, this process usually takes 2-4 minutes...
"%INSTALLER_PATH%" install --quiet --accept-license

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Installation exited with code %ERRORLEVEL%.
    pause
    exit /b 1
)

echo [OK] Docker Desktop installation finished.
del "%INSTALLER_PATH%" >nul 2>&1
set "PATH=C:\Program Files\Docker\Docker\resources\bin;%PATH%"


:START_DOCKER_ENGINE
echo.
echo Checking Docker engine daemon status...
docker info >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Docker daemon is running and responsive.
    goto :SETUP_COMPLETED
)

echo Starting Docker Desktop background service...
if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
) else (
    echo [WARNING] Could not find Docker Desktop.exe at default location.
)

echo Waiting for Docker engine to initialize (this may take up to 60 seconds)...
set /a WAIT_COUNT=0

:WAIT_LOOP
timeout /t 3 /nobreak >nul
docker info >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Docker daemon is now ACTIVE and READY!
    goto :SETUP_COMPLETED
)

set /a WAIT_COUNT+=3
set /p ".=." <nul
if %WAIT_COUNT% GEQ 120 (
    echo.
    echo [WARNING] Docker engine is taking longer than usual to respond.
    echo Please ensure Docker Desktop has completed startup in your system tray,
    echo then re-run this script.
    pause
    exit /b 1
)
goto :WAIT_LOOP


:SETUP_COMPLETED
echo.
echo =================================================================
echo   DOCKER SETUP VERIFIED & READY!
echo =================================================================
for /f "tokens=*" %%v in ('docker --version 2^>nul') do echo %%v
echo.
echo You can now run:
echo   1. docker_test_gpu.bat         (Verify NVIDIA CUDA inside container)
echo   2. docker_transcribe_test.bat  (Run Whisper Large-v3 Full test)
echo   3. docker_run_studio.bat       (Open interactive Studio UI in browser)
echo =================================================================
echo.
pause

