@echo off
title Local Speech Studio - NVIDIA GPU Setup (CUDA 12)
cd /d "%~dp0"

echo =================================================================
echo   LOCAL SPEECH STUDIO - NVIDIA GPU ENVIRONMENT SETUP
echo   Urdu-English Mixed & Roman Urdu Pipeline
echo =================================================================
echo.

:: 1. Verify Python Installation
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python was not found in PATH.
    echo Please install Python 3.10 or 3.11 from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do echo [OK] Found Python: %%i

:: 2. Create or verify Virtual Environment
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [STEP 1/4] Creating local virtual environment at .venv...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment exists at .venv.
)

:: 3. Upgrade pip
echo.
echo [STEP 2/4] Upgrading pip tooling...
".venv\Scripts\python.exe" -m pip install --upgrade pip

:: 4. Install PyTorch with CUDA 12.1
echo.
echo [STEP 3/4] Installing PyTorch with NVIDIA CUDA 12.1 acceleration...
echo This downloads the official CUDA-enabled PyTorch wheels (~2.3 GB).
".venv\Scripts\python.exe" -m pip install torch --index-url https://download.pytorch.org/whl/cu121
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [WARNING] CUDA PyTorch wheel installation encountered an issue.
    echo Retrying standard pip installation...
    ".venv\Scripts\python.exe" -m pip install torch
)

:: 5. Install GPU dependencies and CTranslate2 cuDNN libraries
echo.
echo [STEP 4/4] Installing Faster-Whisper, CTranslate2 & CUDA runtime libraries...
".venv\Scripts\python.exe" -m pip install -r requirements-gpu.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install GPU requirements.
    pause
    exit /b 1
)

:: 6. Run Hardware Verification Diagnostic
echo.
echo =================================================================
echo   RUNNING HARDWARE & CUDA VERIFICATION
echo =================================================================
echo.
".venv\Scripts\python.exe" scripts\verify_gpu.py

echo.
echo =================================================================
echo   SETUP COMPLETED!
echo =================================================================
echo To start the application, double-click: run_ui.bat or run_gpu.bat
echo To pre-download models offline, double-click: download_models.bat
echo =================================================================
echo.
pause

