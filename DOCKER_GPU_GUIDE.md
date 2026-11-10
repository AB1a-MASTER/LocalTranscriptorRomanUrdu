# Local Speech Studio — Docker GPU Distribution Guide

This guide explains how to run **Local Speech Studio** inside a Docker container with **NVIDIA CUDA GPU Acceleration**. 

Using Docker eliminates host Python version incompatibilities (such as Python 3.12 or 3.13 causing wheel or DLL mismatches) by providing an isolated, pinned **Python 3.10 + CUDA 12.1 + cuDNN 8** environment.

---

## ⚡ Prerequisites on the GPU System

1. **NVIDIA GPU Drivers**: Version 525 or newer installed on the host.
2. **Docker**:
   - **On Windows**: Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) (ensure **WSL 2 backend** is enabled in Docker Desktop settings).
   - **On Linux**: Ensure Docker and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) are installed.

---

## 🚀 Quick Start (Windows GPU System)

Copy or extract the `LocalSpeechStudio_Docker_GPU` package to your target GPU system:

### Option A: Complete 1-Click Solution (Recommended)
Double-click:
```cmd
1_CLICK_RUN_DOCKER_GPU.bat
```
This single script does everything automatically:
1. **Checks if Docker is installed**: If not found, it downloads the official Docker Desktop installer, configures WSL2, and installs it unattended.
2. **Starts the Docker engine**: If Docker Desktop is stopped, it starts the background daemon and waits for it to become ready.
3. **Builds the container image**: Automatically compiles the `local-speech-studio:gpu` image if not already built.
4. **Launches the Studio UI**: Starts the GPU-accelerated container and automatically opens `http://localhost:6080/vnc.html` in your default browser.

---

### Option B: Step-by-Step Individual Scripts

If you prefer running individual steps:

1. **Install or Start Docker**:
   Double-click:
   ```cmd
   install_or_start_docker.bat
   ```
   *(Auto-elevates with Administrator rights, installs Docker Desktop via curl if missing, and boots the Docker engine daemon).*

2. **Build the Container Image**:
   Double-click:
   ```cmd
   docker_build.bat
   ```

3. **Verify GPU Acceleration**:
   Double-click:
   ```cmd
   docker_test_gpu.bat
   ```

4. **Run Transcription Test (Whisper Large-v3 Full)**:
   Double-click:
   ```cmd
   docker_transcribe_test.bat
   ```

5. **Start Studio Web UI**:
   Double-click:
   ```cmd
   docker_run_studio.bat
   ```

6. **Reclaiming Disk Space (`docker_clean_space.bat`)**:
   If you previously built the old 24 GB image, double-click:
   ```cmd
   docker_clean_space.bat
   ```
   This utility stops old containers, removes the 24 GB image, and purges the Docker builder cache to reclaim all your disk space. Then re-run `docker_build.bat` to compile the new **~2.5 GB** ultra-lean image.

---

## 🐧 Linux / WSL2 Quick Start

If testing on a Linux machine or inside WSL2:

```bash
# 1. Build image
./docker_run.sh build

# 2. Check GPU diagnostics
./docker_run.sh verify

# 3. Transcribe test.wav with Large-v3
./docker_run.sh test

# 4. Start Web UI Studio
./docker_run.sh studio
# Open http://localhost:6080/vnc.html in your browser

# 5. Stop containers
./docker_run.sh stop
```

*(Note for Linux/WSLg desktop users: you can also run `./docker_run.sh studio-native` to render the window directly on your desktop display via X11).*

---

## 📁 Volume Mounts & Data Persistence

The Docker container maps the following folders between your host PC and the container:

| Host Folder | Container Path | Purpose |
| :--- | :--- | :--- |
| `./input/` | `/app/input/` | Place audio/video media files here to transcribe. |
| `./output/` | `/app/output/` | Transcribed TXT and SRT files are saved directly here on the host. |
| `./cache/huggingface/` | `/root/.cache/huggingface/` | Whisper model weights are cached here so they are downloaded once and run 100% offline. |

---

## 📡 100% Offline / Air-Gapped Setup

To run completely offline without an internet connection on the GPU machine:
1. On an internet-connected PC, double-click `docker_download_models.bat` to pre-download Whisper Large-v3 Full into `./cache/huggingface/`.
2. Save the Docker image:
   ```cmd
   docker save -o local_speech_studio_gpu.tar local-speech-studio:gpu
   ```
3. Copy the project folder and `local_speech_studio_gpu.tar` to your offline GPU machine.
4. Load the image on the offline machine:
   ```cmd
   docker load -i local_speech_studio_gpu.tar
   ```
5. Run `docker_transcribe_test.bat` or `docker_run_studio.bat` — it will run 100% locally with zero internet access.

