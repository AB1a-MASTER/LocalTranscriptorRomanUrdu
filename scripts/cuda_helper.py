"""
CUDA & DLL Helper for Windows Desktop Deployment
================================================
Ensures NVIDIA CUDA/cuDNN DLLs installed via pip (or PyTorch) are discoverable by
CTranslate2 and faster-whisper on Windows systems.
"""

import os
import sys
import site
import shutil
from pathlib import Path

_INITIALIZED = False


def init_cuda_dlls():
    """
    Scans and registers NVIDIA cuBLAS / cuDNN runtime DLL directories with os.add_dll_directory
    and prepends them to os.environ['PATH'] on Windows.
    This prevents 'cublas64_*.dll not found' and 'cudnn_ops_infer64_*.dll not found' runtime errors.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True

    if sys.platform != "win32":
        return

    candidate_roots = []

    # 1. Standard site-packages
    try:
        candidate_roots.extend(site.getsitepackages())
    except Exception:
        pass

    try:
        user_site = site.getusersitepackages()
        if user_site:
            candidate_roots.append(user_site)
    except Exception:
        pass

    # 2. Virtual environment Lib/site-packages
    py_exe = Path(sys.executable).resolve()
    candidate_roots.append(py_exe.parent / "Lib" / "site-packages")
    candidate_roots.append(py_exe.parent.parent / "Lib" / "site-packages")

    added = set()

    def _add_dir(d: Path):
        try:
            resolved = str(d.resolve())
            if resolved in added:
                return
            if not d.exists() or not d.is_dir():
                return
            added.add(resolved)
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(resolved)
                except Exception:
                    pass
            cur_path = os.environ.get("PATH", "")
            if resolved not in cur_path:
                os.environ["PATH"] = resolved + os.pathsep + cur_path
        except Exception:
            pass

    for r in candidate_roots:
        root_path = Path(r)
        if not root_path.exists():
            continue

        # Check pip-installed nvidia packages (nvidia-cublas-cu12, nvidia-cudnn-cu12, etc.)
        nvidia_path = root_path / "nvidia"
        if nvidia_path.exists() and nvidia_path.is_dir():
            try:
                for sub in nvidia_path.iterdir():
                    bin_dir = sub / "bin"
                    if bin_dir.exists() and bin_dir.is_dir():
                        _add_dir(bin_dir)
            except Exception:
                pass

        # Check PyTorch bundled CUDA libraries (torch/lib)
        torch_lib = root_path / "torch" / "lib"
        if torch_lib.exists() and torch_lib.is_dir():
            _add_dir(torch_lib)

    # 3. Check system CUDA_PATH if NVIDIA CUDA Toolkit is installed
    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        cuda_bin = Path(cuda_path) / "bin"
        if cuda_bin.exists():
            _add_dir(cuda_bin)


def get_ffmpeg_binary() -> str:
    """
    Finds a working ffmpeg binary on the machine.
    Search priority:
      1. Local bin/ffmpeg.exe (packaged)
      2. System PATH ffmpeg
      3. imageio_ffmpeg bundled binary (if installed)
      4. Fallback to 'ffmpeg'
    """
    # 1. Local bin folder
    current_file = Path(__file__).resolve()
    root_dir = current_file.parent.parent
    local_bin = root_dir / "bin" / "ffmpeg.exe"
    if local_bin.exists():
        return str(local_bin)

    # 2. System PATH
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg

    # 3. imageio_ffmpeg
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:
        pass

    return "ffmpeg"


# Run DLL registration automatically on import
init_cuda_dlls()

