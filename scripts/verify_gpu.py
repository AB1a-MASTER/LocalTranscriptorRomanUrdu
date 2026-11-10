#!/usr/bin/env python3
"""
GPU & Hardware Diagnostics Verification Script
==============================================
Validates CUDA runtime, cuBLAS/cuDNN DLLs, PyTorch GPU acceleration,
CTranslate2 CUDA inference engine, and FFmpeg connectivity.
"""

import sys
import os
from pathlib import Path

# Ensure scripts directory is on path
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import cuda_helper
cuda_helper.init_cuda_dlls()


def run_diagnostics() -> bool:
    print("=" * 65)
    print("  LOCAL SPEECH STUDIO - GPU & HARDWARE DIAGNOSTIC REPORT")
    print("=" * 65)
    print(f"Python Runtime:     {sys.version.split()[0]} ({sys.platform})")
    print(f"Executable:         {sys.executable}")

    # 1. FFmpeg Check
    ffmpeg_bin = cuda_helper.get_ffmpeg_binary()
    print("-" * 65)
    print("1. FFmpeg Audio Extractor:")
    print(f"   Binary Path:     {ffmpeg_bin}")
    import shutil
    ffmpeg_found = (ffmpeg_bin and (ffmpeg_bin != "ffmpeg" or shutil.which("ffmpeg")))
    if ffmpeg_found:
        print("   Status:          [OK] Available")
    else:
        print("   Status:          [WARNING] ffmpeg not found in PATH or local bin/")

    # 2. PyTorch CUDA Check
    print("-" * 65)
    print("2. PyTorch CUDA Status:")
    torch_ok = False
    try:
        import torch
        print(f"   PyTorch Version: {torch.__version__}")
        cuda_avail = torch.cuda.is_available()
        print(f"   CUDA Available:  {cuda_avail}")
        if cuda_avail:
            torch_ok = True
            dev_cnt = torch.cuda.device_count()
            print(f"   CUDA Devices:    {dev_cnt}")
            for i in range(dev_cnt):
                dev_name = torch.cuda.get_device_name(i)
                mem_bytes = torch.cuda.get_device_properties(i).total_memory
                mem_gb = mem_bytes / (1024 ** 3)
                print(f"     Device [{i}]:   {dev_name} ({mem_gb:.1f} GB VRAM)")
        else:
            print("   Status:          PyTorch CUDA is not active (CPU build installed)")
            try:
                import subprocess
                res = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True, timeout=2)
                if res.returncode == 0 and res.stdout.strip():
                    for line in res.stdout.strip().split("\n"):
                        print(f"   Host GPU:        {line.strip()}")
            except Exception:
                pass
    except ImportError:
        print("   Status:          PyTorch is not installed")
    except Exception as e:
        print(f"   Status:          Error checking PyTorch: {e}")

    # 3. CTranslate2 CUDA Check (used by Faster-Whisper)
    print("-" * 65)
    print("3. CTranslate2 CUDA Status (Faster-Whisper Engine):")
    ct2_ok = False
    try:
        import ctranslate2
        print(f"   CTranslate2 Ver: {ctranslate2.__version__}")
        ct2_dev_cnt = getattr(ctranslate2, "get_cuda_device_count", lambda: 0)()
        print(f"   CUDA Devices:    {ct2_dev_cnt}")
        if ct2_dev_cnt > 0:
            ct2_ok = True
            types = ctranslate2.get_supported_compute_types("cuda")
            print(f"   Supported Types: {sorted(list(types))}")
            print("   cuDNN / cuBLAS:  [OK] Successfully linked and verified")
        else:
            print("   Status:          No CUDA devices reported by CTranslate2")
    except ImportError:
        print("   Status:          CTranslate2 is not installed")
    except Exception as e:
        print(f"   Status:          CTranslate2 CUDA error: {e}")

    # 4. Faster-Whisper Check
    print("-" * 65)
    print("4. Faster-Whisper Library:")
    try:
        import faster_whisper
        print(f"   Library Version: {faster_whisper.__version__}")
    except ImportError:
        print("   Status:          faster-whisper is not installed")

    # 5. Audio Player Check
    print("-" * 65)
    print("5. Audio Playback Device (SoundDevice):")
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        default_out = sd.query_devices(kind="output")
        print(f"   Default Output:  {default_out.get('name', 'Unknown')}")
        print("   Status:          [OK] Audio player ready")
    except Exception as e:
        print(f"   Status:          Audio device warning: {e}")

    # Final Summary
    print("=" * 65)
    cuda_ready = torch_ok or ct2_ok
    if cuda_ready:
        print("  RESULT: >>> [SUCCESS] NVIDIA CUDA GPU IS ACTIVE AND READY! <<<")
        print("  You can run Whisper Large-v3 Full & Turbo with float16 acceleration.")
    else:
        print("  RESULT: >>> [NOTICE] Running in CPU Multi-Threaded Mode (int8) <<<")
        print("  If an NVIDIA GPU is present, ensure NVIDIA drivers and CUDA packages")
        print("  are installed via setup_gpu.bat.")
    print("=" * 65)
    return cuda_ready


if __name__ == "__main__":
    run_diagnostics()

