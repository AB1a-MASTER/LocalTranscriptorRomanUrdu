@echo off
title Local Speech Studio - Hardware & CUDA Check
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\verify_gpu.py
) else (
    python scripts\verify_gpu.py
)
pause

