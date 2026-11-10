#!/usr/bin/env python3
"""
Distribution Packaging Script
=============================
Packages Local Speech Studio into clean, portable distribution directories
and compressed ZIP archives:
  1. Docker GPU Distribution (immune to host Python version mismatches)
  2. Native Windows GPU Distribution
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"


def package_docker():
    pkg_name = "LocalSpeechStudio_Docker_GPU"
    target_dir = DIST_DIR / pkg_name
    zip_path = DIST_DIR / f"{pkg_name}.zip"

    print("=" * 65)
    print("  PACKAGING DOCKER GPU DISTRIBUTION")
    print("=" * 65)

    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Root Docker files
    docker_files = [
        ".dockerignore",
        "1_CLICK_RUN_DOCKER_GPU.bat",
        "install_or_start_docker.bat",
        "docker_clean_space.bat",
        "Dockerfile",
        "docker-compose.yml",
        "docker-entrypoint.sh",
        "requirements-docker.txt",
        "docker_build.bat",
        "docker_test_gpu.bat",
        "docker_transcribe_test.bat",
        "docker_run_studio.bat",
        "docker_stop_studio.bat",
        "docker_download_models.bat",
        "docker_run.sh",
        "DOCKER_GPU_GUIDE.md",
    ]

    for df in docker_files:
        src = ROOT / df
        if src.exists():
            shutil.copy2(src, target_dir / df)
            print(f"  + Added: {df}")

    # 2. Scripts
    target_scripts = target_dir / "scripts"
    target_scripts.mkdir(parents=True, exist_ok=True)
    src_scripts = ROOT / "scripts"
    for item in src_scripts.iterdir():
        if item.is_file() and item.suffix in (".py", ".json", ".txt"):
            shutil.copy2(item, target_scripts / item.name)
            print(f"  + Added script: scripts/{item.name}")

    # 3. Input folder
    target_input = target_dir / "input"
    target_input.mkdir(parents=True, exist_ok=True)
    test_wav = ROOT / "input" / "test.wav"
    if test_wav.exists():
        shutil.copy2(test_wav, target_input / "test.wav")
        print("  + Added test audio: input/test.wav")

    # 4. Output folder
    target_output = target_dir / "output"
    target_output.mkdir(parents=True, exist_ok=True)
    with open(target_output / ".gitkeep", "w", encoding="utf-8") as f:
        f.write("# Output directory for transcripts and subtitles\n")

    # 5. Cache directory placeholder
    target_cache = target_dir / "cache" / "huggingface"
    target_cache.mkdir(parents=True, exist_ok=True)
    with open(target_cache / ".gitkeep", "w", encoding="utf-8") as f:
        f.write("# Local cache for downloaded models\n")

    # 6. ZIP archive
    print(f"\nCreating ZIP archive: {zip_path.name}...")
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in target_dir.rglob("*"):
            if file.is_file():
                arcname = file.relative_to(DIST_DIR)
                zf.write(file, arcname)

    zip_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  DOCKER PACKAGE READY: {target_dir}")
    print(f"  ARCHIVE CREATED:      {zip_path} ({zip_mb:.2f} MB)")


def package_native():
    pkg_name = "LocalSpeechStudio_GPU"
    target_dir = DIST_DIR / pkg_name
    zip_path = DIST_DIR / f"{pkg_name}.zip"

    print("\n" + "=" * 65)
    print("  PACKAGING NATIVE WINDOWS GPU DISTRIBUTION")
    print("=" * 65)

    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    root_files = [
        "setup_gpu.bat",
        "run_gpu.bat",
        "run_ui.bat",
        "download_models.bat",
        "verify_hardware.bat",
        "requirements-gpu.txt",
        "requirements.txt",
        "README_GPU_SETUP.md",
        "QUICKSTART.txt",
    ]

    for rf in root_files:
        src = ROOT / rf
        if src.exists():
            shutil.copy2(src, target_dir / rf)
            print(f"  + Added: {rf}")

    target_scripts = target_dir / "scripts"
    target_scripts.mkdir(parents=True, exist_ok=True)
    src_scripts = ROOT / "scripts"
    for item in src_scripts.iterdir():
        if item.is_file() and item.suffix in (".py", ".json", ".txt"):
            shutil.copy2(item, target_scripts / item.name)

    target_input = target_dir / "input"
    target_input.mkdir(parents=True, exist_ok=True)
    test_wav = ROOT / "input" / "test.wav"
    if test_wav.exists():
        shutil.copy2(test_wav, target_input / "test.wav")

    target_output = target_dir / "output"
    target_output.mkdir(parents=True, exist_ok=True)
    with open(target_output / ".gitkeep", "w", encoding="utf-8") as f:
        f.write("# Output directory for transcripts and subtitles\n")

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in target_dir.rglob("*"):
            if file.is_file():
                arcname = file.relative_to(DIST_DIR)
                zf.write(file, arcname)

    zip_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  NATIVE PACKAGE READY: {target_dir}")
    print(f"  ARCHIVE CREATED:      {zip_path} ({zip_mb:.2f} MB)")


if __name__ == "__main__":
    package_docker()
    package_native()
    print("\n" + "=" * 65)
    print("  ALL PACKAGES CREATED SUCCESSFULLY!")
    print("=" * 65)
