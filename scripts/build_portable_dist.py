#!/usr/bin/env python3
"""
Portable Windows Distribution Builder (Zero-Docker, Zero-Setup)
==============================================================
Bundles a fully self-contained Python 3.11 runtime, all pre-installed
wheels (faster-whisper, ctranslate2, sounddevice, etc.), Tkinter GUI,
and FFmpeg into dist/LocalSpeechStudio_Portable.

Runs anywhere on Windows without installing Python or Docker.
"""

import os
import sys
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
TARGET_DIR = DIST_DIR / "LocalSpeechStudio_Portable"
PYTHON_HOST = Path("C:/Users/pc/AppData/Local/Programs/Python/Python311")
VENV_SITE_PACKAGES = ROOT / ".venv" / "Lib" / "site-packages"


def build_portable():
    print("=" * 65)
    print("  BUILDING STANDALONE PORTABLE WINDOWS DISTRIBUTION")
    print("  (Zero-Docker, Zero-Setup, Self-Contained Runtime)")
    print("=" * 65)

    if TARGET_DIR.exists():
        print(f"Cleaning previous build at: {TARGET_DIR}...")
        shutil.rmtree(TARGET_DIR, ignore_errors=True)
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    runtime_dir = TARGET_DIR / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy core Python binaries
    print("\n[1/6] Bundling Python 3.11 core binaries...")
    bin_files = [
        "python.exe", "pythonw.exe", "python3.dll", "python311.dll",
        "vcruntime140.dll", "vcruntime140_1.dll"
    ]
    for bf in bin_files:
        src = PYTHON_HOST / bf
        if src.exists():
            shutil.copy2(src, runtime_dir / bf)

    # 2. Copy DLLs and Tcl/Tk for GUI
    print("[2/6] Bundling C-extensions, Tkinter & Tcl/Tk GUI...")
    dlls_src = PYTHON_HOST / "DLLs"
    if dlls_src.exists():
        shutil.copytree(dlls_src, runtime_dir / "DLLs", dirs_exist_ok=True)

    tcl_src = PYTHON_HOST / "tcl"
    if tcl_src.exists():
        shutil.copytree(tcl_src, runtime_dir / "tcl", dirs_exist_ok=True)

    # 3. Copy Standard Library (excluding site-packages)
    print("[3/6] Bundling Python standard library...")
    lib_src = PYTHON_HOST / "Lib"
    lib_dest = runtime_dir / "Lib"
    lib_dest.mkdir(parents=True, exist_ok=True)

    # Use robocopy to copy standard library excluding site-packages
    cmd_lib = [
        "robocopy", str(lib_src), str(lib_dest),
        "/E", "/XD", "site-packages", "__pycache__",
        "/NFL", "/NDL", "/NJH", "/NJS", "/nc", "/ns", "/np"
    ]
    subprocess.run(cmd_lib, capture_output=True)

    # 4. Copy pre-installed site-packages (faster-whisper, ctranslate2, etc.)
    print("[4/6] Bundling pre-compiled wheels & dependencies (Faster-Whisper, CTranslate2, SoundDevice)...")
    site_dest = lib_dest / "site-packages"
    site_dest.mkdir(parents=True, exist_ok=True)

    cmd_site = [
        "robocopy", str(VENV_SITE_PACKAGES), str(site_dest),
        "/E", "/XD", "__pycache__",
        "/NFL", "/NDL", "/NJH", "/NJS", "/nc", "/ns", "/np"
    ]
    subprocess.run(cmd_site, capture_output=True)

    # 5. Create relative path resolver python311._pth
    print("[5/6] Configuring isolated, relative path routing (python311._pth)...")
    pth_content = "\n".join([
        ".",
        "DLLs",
        "Lib",
        "Lib\\site-packages",
        "..\\scripts",
        "import site",
        ""
    ])
    with open(runtime_dir / "python311._pth", "w", encoding="utf-8") as f:
        f.write(pth_content)

    # 6. Bundle FFmpeg binary
    print("[6/6] Bundling FFmpeg binary...")
    bin_dir = TARGET_DIR / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    # Look for ffmpeg in WinGet packages
    ffmpeg_search = list(Path("C:/Users/pc/AppData/Local/Microsoft/WinGet/Packages").glob("**/ffmpeg.exe"))
    if ffmpeg_search:
        shutil.copy2(ffmpeg_search[0], bin_dir / "ffmpeg.exe")
        print(f"  + Added FFmpeg: {ffmpeg_search[0].name}")
    else:
        print("  ! FFmpeg fallback will use system PATH")

    # Copy project files: scripts, ui_web, input, output, models
    scripts_dest = TARGET_DIR / "scripts"
    shutil.copytree(ROOT / "scripts", scripts_dest, dirs_exist_ok=True)

    ui_web_dest = TARGET_DIR / "ui_web"
    shutil.copytree(ROOT / "ui_web", ui_web_dest, dirs_exist_ok=True)

    input_dest = TARGET_DIR / "input"
    input_dest.mkdir(parents=True, exist_ok=True)
    if (ROOT / "input" / "test.wav").exists():
        shutil.copy2(ROOT / "input" / "test.wav", input_dest / "test.wav")

    output_dest = TARGET_DIR / "output"
    output_dest.mkdir(parents=True, exist_ok=True)
    with open(output_dest / ".gitkeep", "w", encoding="utf-8") as f:
        f.write("# Output directory for transcripts and subtitles\n")

    models_dest = TARGET_DIR / "models"
    models_dest.mkdir(parents=True, exist_ok=True)
    with open(models_dest / "README.txt", "w", encoding="utf-8") as f:
        f.write(
            "Local Speech Studio - Models Directory\n"
            "======================================\n"
            "This folder stores downloaded AI models for 100% offline speech recognition.\n\n"
            "How to populate this folder:\n"
            "1. ONLINE: Double-click 'download_large_model.bat' or 'download_models.bat' in the main folder.\n"
            "2. OFFLINE: If transferring to an air-gapped machine, copy downloaded model folders\n"
            "   (e.g., 'models--Systran--faster-whisper-large-v3') directly into this 'models' folder.\n"
        )

    # Create launch batch scripts
    _create_launchers()

    # Measure total size
    total_bytes = sum(f.stat().st_size for f in TARGET_DIR.rglob("*") if f.is_file())
    total_mb = total_bytes / (1024 * 1024)
    total_gb = total_bytes / (1024 * 1024 * 1024)

    # Create ZIP archive
    zip_path = DIST_DIR / "LocalSpeechStudio_Portable.zip"
    print(f"\nCompressing standalone bundle to: {zip_path.name}...")
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in TARGET_DIR.rglob("*"):
            if file.is_file():
                arcname = file.relative_to(DIST_DIR)
                zf.write(file, arcname)

    zip_mb = zip_path.stat().st_size / (1024 * 1024)
    zip_gb = zip_mb / 1024

    print("\n" + "=" * 65)
    print("  STANDALONE PORTABLE BUNDLE SUCCESSFULLY CREATED!")
    print(f"  Folder:         {TARGET_DIR} ({total_mb:.1f} MB / {total_gb:.2f} GB)")
    print(f"  Zip Archive:    {zip_path} ({zip_mb:.1f} MB / {zip_gb:.2f} GB)")
    print("=" * 65)


def _create_launchers():
    # 1. run_studio.bat (Main Modern Web Desktop UI)
    run_studio_bat = """@echo off
title Local Speech Studio 2.0 - Portable Standalone
cd /d "%~dp0"

set "PATH=%~dp0bin;%~dp0runtime;%~dp0runtime\\DLLs;%PATH%"
set "HF_HOME=%~dp0models"

echo =================================================================
echo   STARTING LOCAL SPEECH STUDIO 2.0 (MODERN DESKTOP STUDIO)
echo =================================================================
echo   No clipping - Fluid 60fps - Real Waveform - Karaoke Highlight
echo   Opening interface: http://127.0.0.1:7860
echo.

"%~dp0runtime\\python.exe" scripts\\studio_web.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with code %ERRORLEVEL%.
    pause
)
"""
    with open(TARGET_DIR / "run_studio.bat", "w", encoding="utf-8") as f:
        f.write(run_studio_bat)

    # 1b. run_studio_legacy_tk.bat (Fallback Legacy Tkinter UI)
    run_tk_bat = """@echo off
title Local Speech Studio - Legacy Tkinter UI
cd /d "%~dp0"

set "PATH=%~dp0bin;%~dp0runtime;%~dp0runtime\\DLLs;%PATH%"
set "HF_HOME=%~dp0models"

"%~dp0runtime\\python.exe" scripts\\ui.py
pause
"""
    with open(TARGET_DIR / "run_studio_legacy_tk.bat", "w", encoding="utf-8") as f:
        f.write(run_tk_bat)

    # 2. test_transcribe.bat (CLI Test on input/test.wav)
    test_bat = """@echo off
title Local Speech Studio - Whisper Large-v3 Full Test
cd /d "%~dp0"

set "PATH=%~dp0bin;%~dp0runtime;%~dp0runtime\\DLLs;%PATH%"
set "HF_HOME=%~dp0models"

echo =================================================================
echo   TESTING WHISPER LARGE-V3 FULL (1550M) ON NATIVE GPU / CPU
echo =================================================================
echo.

"%~dp0runtime\\python.exe" scripts\\transcribe_pipeline.py input\\test.wav --model large-v3

echo.
echo Outputs generated in: %~dp0output\\
pause
"""
    with open(TARGET_DIR / "test_transcribe.bat", "w", encoding="utf-8") as f:
        f.write(test_bat)

    # 3. download_large_model.bat (1-Click Whisper Large-v3 Full 1550M Downloader)
    dl_large_bat = """@echo off
title Download Whisper Large-v3 Full (1550M) - Local Speech Studio
cd /d "%~dp0"

set "PATH=%~dp0bin;%~dp0runtime;%~dp0runtime\\DLLs;%PATH%"
set "HF_HOME=%~dp0models"

echo =================================================================
echo   DOWNLOADING WHISPER LARGE-V3 FULL (1550M • ~3.1 GB)
echo =================================================================
echo Destination: %~dp0models
echo.
echo Downloading Faster-Whisper Large-v3 weights...
"%~dp0runtime\\python.exe" scripts\\download_models.py --model large-v3 --models-dir "%~dp0models"

echo.
pause
"""
    with open(TARGET_DIR / "download_large_model.bat", "w", encoding="utf-8") as f:
        f.write(dl_large_bat)

    # 4. download_turbo_model.bat (1-Click Whisper Large-v3-Turbo 809M Downloader)
    dl_turbo_bat = """@echo off
title Download Whisper Large-v3-Turbo (809M) - Local Speech Studio
cd /d "%~dp0"

set "PATH=%~dp0bin;%~dp0runtime;%~dp0runtime\\DLLs;%PATH%"
set "HF_HOME=%~dp0models"

echo =================================================================
echo   DOWNLOADING WHISPER LARGE-V3-TURBO (809M • ~1.6 GB)
echo =================================================================
echo Destination: %~dp0models
echo.
echo Downloading Faster-Whisper Large-v3-Turbo weights...
"%~dp0runtime\\python.exe" scripts\\download_models.py --model large-v3-turbo --models-dir "%~dp0models"

echo.
pause
"""
    with open(TARGET_DIR / "download_turbo_model.bat", "w", encoding="utf-8") as f:
        f.write(dl_turbo_bat)

    # 5. download_models.bat (Interactive Downloader Menu)
    dl_menu_bat = """@echo off
title Download Models - Local Speech Studio
cd /d "%~dp0"

set "PATH=%~dp0bin;%~dp0runtime;%~dp0runtime\\DLLs;%PATH%"
set "HF_HOME=%~dp0models"

"%~dp0runtime\\python.exe" scripts\\download_models.py --models-dir "%~dp0models"

echo.
pause
"""
    with open(TARGET_DIR / "download_models.bat", "w", encoding="utf-8") as f:
        f.write(dl_menu_bat)

    # 6. verify_hardware.bat
    verify_bat = """@echo off
title Local Speech Studio - Hardware & CUDA Diagnostics
cd /d "%~dp0"

set "PATH=%~dp0bin;%~dp0runtime;%~dp0runtime\\DLLs;%PATH%"
set "HF_HOME=%~dp0models"

"%~dp0runtime\\python.exe" scripts\\verify_gpu.py
pause
"""
    with open(TARGET_DIR / "verify_hardware.bat", "w", encoding="utf-8") as f:
        f.write(verify_bat)

    # 7. install_gpu_cuda_wheels.bat (Optional 1-click helper for cuBLAS/cuDNN)
    install_cuda_bat = """@echo off
title Install NVIDIA CUDA 12 Wheels into Portable Runtime
cd /d "%~dp0"

echo =================================================================
echo   INSTALLING NVIDIA CUDA 12 DLLS INTO PORTABLE RUNTIME
echo =================================================================
echo.
echo Installing nvidia-cublas-cu12 and nvidia-cudnn-cu12...
"%~dp0runtime\\python.exe" -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12

echo.
echo Checking GPU recognition...
"%~dp0runtime\\python.exe" scripts\\verify_gpu.py
pause
"""
    with open(TARGET_DIR / "install_gpu_cuda_wheels.bat", "w", encoding="utf-8") as f:
        f.write(install_cuda_bat)

    # 8. README_PORTABLE.md
    readme_md = """# Local Speech Studio — Standalone Portable Windows Edition

A 100% self-contained desktop speech-to-text studio. 
**No Docker required. No Python installation required.**

---

## 🚀 Quick Start Guide

### Step 1: Model Setup (Choose One Workflow)

#### Workflow A: Online Machine (1-Click Download)
If the machine is connected to the internet:
1. Double-click `download_large_model.bat` to download **Whisper Large-v3 Full (1550M, ~3.1 GB)**.
   *(Or double-click `download_turbo_model.bat` for the faster 809M Turbo model).*
2. The model downloads directly into the local `models/` directory.

#### Workflow B: Offline / Air-Gapped GPU Machine (Zero Internet)
If your GPU machine does not have internet:
1. Run `download_large_model.bat` on an internet-connected machine.
2. Copy the resulting `models/` folder onto a USB stick or external drive.
3. Paste the `models/` folder into `LocalSpeechStudio_Portable/models/` on the GPU machine.
4. The studio will run completely offline without contacting any servers.

---

### Step 2: Run the Studio

- **Launch the Desktop UI**:
  Double-click:
  ```cmd
  run_studio.bat
  ```

- **Run Quick GPU/CPU Transcription Test**:
  Double-click:
  ```cmd
  test_transcribe.bat
  ```
  *(Transcribes `input/test.wav` using Whisper Large-v3 Full and writes Urdu & Roman Urdu subtitles to `output/`).*

- **Verify GPU & CUDA Status**:
  Double-click:
  ```cmd
  verify_hardware.bat
  ```

---

## ⚡ NVIDIA GPU Acceleration (Optional)

The portable bundle automatically uses your NVIDIA GPU if CUDA runtime DLLs are present.
If your GPU machine does not have CUDA Toolkit in PATH:
Double-click:
```cmd
install_gpu_cuda_wheels.bat
```
*(Installs NVIDIA cuBLAS & cuDNN directly into the bundled runtime without touching the host system).*
"""
    with open(TARGET_DIR / "README_PORTABLE.md", "w", encoding="utf-8") as f:
        f.write(readme_md)


if __name__ == "__main__":
    build_portable()
