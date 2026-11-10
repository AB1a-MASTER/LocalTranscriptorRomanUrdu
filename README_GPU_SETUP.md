# Local Speech Studio — NVIDIA GPU Testing & Deployment Guide

This guide walks you through setting up and running **Local Speech Studio** with **NVIDIA CUDA GPU Acceleration** and testing the high-accuracy model (**Whisper Large-v3 Full** / **Whisper Large-v3-Turbo**).

---

## ⚡ 3-Step Quick Start on Target GPU Machine

### Step 1: Prerequisites
- **Operating System**: Windows 10 or Windows 11 (64-bit).
- **GPU**: NVIDIA GPU (RTX 20/30/40 series, GTX 16xx, Quadro, Tesla, A-series) with NVIDIA Driver version **525 or newer**.
- **Python**: Python 3.10, 3.11, or 3.12 installed from [python.org](https://www.python.org/downloads/).
  *(Make sure **"Add Python to PATH"** was checked during Python installation).*

---

### Step 2: One-Click Environment Setup
1. Copy or extract the `LocalSpeechStudio` folder to your GPU machine (e.g., `D:\LocalSpeechStudio` or `C:\LocalSpeechStudio`).
2. Double-click:
   ```cmd
   setup_gpu.bat
   ```
3. The setup script will automatically:
   - Create a clean local Python virtual environment (`.venv`).
   - Install **PyTorch with CUDA 12.1** acceleration.
   - Install **Faster-Whisper (CTranslate2)** along with **NVIDIA cuBLAS & cuDNN DLLs**.
   - Install audio playback (`sounddevice`), audio decoder (`imageio-ffmpeg`), and NLP libraries.
   - Run a hardware diagnostic check to confirm that your NVIDIA GPU is recognized.

---

### Step 3: Start the Application & Test the Better Model
1. Double-click:
   ```cmd
   run_gpu.bat
   ```
   *(or `run_ui.bat`)*

2. In the Studio window:
   - Look at the top-right header or bottom status bar: you should see **`🟢 CUDA Active: [Your GPU Name] (float16)`**.
   - In the right-hand **Inspector Panel** under **ASR Model**, select:
     - **`Whisper Large-v3 (High Accuracy • 1550M • GPU/CPU)`** *(Recommended for highest accuracy)*
     - or **`Whisper Large-v3-Turbo (Faster-Whisper • 809M)`** *(For ultra-fast processing)*
   - Click **`📁 Browse Media Files...`** and select an audio or video file (from `input/test.wav` or your own test files).
   - Click **`▶ Transcribe Audio`**.
   - Whisper Large-v3 will run directly on your NVIDIA Tensor Cores in **float16** precision!

---

## 📦 Running 100% Offline (Air-Gapped Machines)

If the target GPU machine does not have an active internet connection:
1. **Pre-download the models on an internet-connected machine**:
   - Double-click `download_models.bat` (or run `python scripts\download_models.py --model large-v3`).
   - Models are stored in your user cache:
     ```
     %USERPROFILE%\.cache\huggingface\hub\
     ```
     *(specifically: `models--Systran--faster-whisper-large-v3` and `models--Systran--faster-whisper-large-v3-turbo`)*
2. **Copy the cache folder**:
   - Copy the folder `%USERPROFILE%\.cache\huggingface\hub\` onto a USB drive.
   - On the offline target machine, paste it into `%USERPROFILE%\.cache\huggingface\hub\`.
   - The Studio will automatically detect and load the cached models without attempting any network connection.

---

## 🛠️ Diagnostics & Verification Tools

- **Verify GPU & Hardware**:
  Double-click `verify_hardware.bat`. It checks PyTorch CUDA, CTranslate2 CUDA device count, cuDNN linkage, and FFmpeg reachability.
- **Hardware Dialog in UI**:
  Click the **`⚡ Hardware`** button in the top navigation bar inside the app at any time to inspect live device details, VRAM, and active acceleration mode.

---

## ❓ Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **"No CUDA devices reported"** | Outdated NVIDIA GPU driver | Download and install the latest NVIDIA Game Ready or Studio Driver from [nvidia.com/drivers](https://www.nvidia.com/Download/index.aspx). |
| **"Python was not found in PATH"** | Python not added to system PATH | Re-run the Python installer, click "Modify", check "Add Python to environment variables", and finish. |
| **"ffmpeg not found"** | System PATH does not include FFmpeg | The package automatically uses `imageio-ffmpeg` as a fallback, or you can place `ffmpeg.exe` directly into the `bin/` folder. |
| **Memory Error (OOM)** | Audio file is extremely long or VRAM < 4 GB | Use **Whisper Large-v3-Turbo (809M)** which only requires ~2.5 GB VRAM, or switch Compute Device to **CPU Mode**. |

