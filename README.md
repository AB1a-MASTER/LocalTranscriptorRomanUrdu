# Local Speech Studio 2.0
### Offline Speech-to-Text & Subtitle Studio for Urdu, English & Roman Urdu

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-brightgreen.svg)](https://www.python.org/)
[![Faster-Whisper](https://img.shields.io/badge/Engine-Faster--Whisper-orange.svg)](https://github.com/SYSTRAN/faster-whisper)
[![CUDA](https://img.shields.io/badge/GPU-NVIDIA%20CUDA%20Accelerated-76B900.svg)](https://developer.nvidia.com/cuda-zone)

**Local Speech Studio** is a 100% offline, privacy-first speech recognition and subtitling desktop studio specifically optimized for **Pakistani English-Urdu code-switching**, lectures, interviews, and conversational dialogue.

---

## ✨ Features

- **🎨 Modern Web Desktop Studio**:
  - Responsive 3-column MacWhisper-style interface with zero scaling or clipping issues on high-DPI displays.
  - Instant Light / Dark mode toggle.
  - Real-time streaming progress with rolling dynamic ETA and decoding speed tracking.

- **🎤 Word-by-Word Karaoke Synchronization**:
  - Frame-accurate word-level timestamps (`word_timestamps=True`).
  - 60 FPS real-time karaoke glow pill on words as they are spoken.
  - Active section auto-scroll and visual illumination.
  - Interactive click-to-seek: click any word or section header to jump playback instantly.

- **✏️ Inline Transcript Editor**:
  - Edit any subtitle segment directly in the browser with side-by-side editing for **Urdu Nastaliq script** (Right-to-Left) and **Roman Urdu / English**.
  - One-click auto-save (`POST /api/save-transcript`) updates all files on disk and recalculates word tokens seamlessly.

- **📦 Multi-Format Export Center**:
  - **Roman Urdu SRT** (`.srt`): Word- or segment-level subtitles in Roman Urdu / English.
  - **Urdu Script SRT** (`.srt`): Nastaliq script subtitles.
  - **WebVTT** (`.vtt`): Standard for HTML5 video, YouTube, Vimeo, and Canvas LMS.
  - **Word-Level JSON** (`.json`): Millisecond start/end timestamps for DaVinci Resolve & Premiere Pro scripts.
  - **Review Table** (`.csv`): Tabular export for spreadsheet review.
  - **Plain Text** (`.txt`): Unformatted text transcripts.
  - **1-Click Clipboard Copy**: Instantly copy full Roman text, Urdu text, or SRT subtitles.

- **⚡ High-Speed & High-Accuracy ASR Engine**:
  - Powered by **Faster-Whisper (CTranslate2)**.
  - **Fast Greedy Decoding** (`beam_size=1` with automatic temperature fallback): 3x–5x speedup, 60% lower VRAM, and eliminates phrase repetition loops.
  - **Silero VAD Silence Suppression**: Strips background hiss and hums, preventing hallucinations over pauses.
  - **Domain Code-Switching Prompt Injection**: Preserves English technical, academic, and business vocabulary (e.g. *SKANS, ACCA, exam, paper, link, campus, fees*).
  - **Phonetic Post-Processing Engine**: Automatically cleans common acoustic slips.

- **🔒 100% Offline & Private**:
  - Runs entirely on your local machine. No audio, video, or text is ever sent to external cloud APIs.

---

## 🚀 Quickstart

### Prerequisites
- Windows 10/11 or Linux
- Python 3.10 or 3.11
- FFmpeg installed and available on system PATH
- *(Optional)* NVIDIA GPU with CUDA 12+ for 15x–20x real-time transcription speed

### Option 1: Native Windows Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/AB1a-MASTER/LocalTranscriptorRomanUrdu.git
   cd LocalTranscriptorRomanUrdu
   ```

2. **Create and Activate Virtual Environment**:
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```cmd
   pip install -r requirements.txt
   ```
   *(For NVIDIA GPU acceleration, also install:* `pip install -r requirements-gpu.txt`*)*

4. **Launch the Studio**:
   ```cmd
   run_studio_web.bat
   ```
   The studio will automatically open in your default browser at `http://127.0.0.1:7860`.

---

### Option 2: Docker GPU (Zero-Setup)

If you have Docker Desktop with NVIDIA GPU Container Toolkit installed:

```cmd
1_CLICK_RUN_DOCKER_GPU.bat
```
*(Or use `docker_run_studio.bat` to build and launch the container).*

---

## ⌨️ Editor Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Space` or `K` | Play / Pause playback |
| `J` or `←` | Skip backward 5 seconds |
| `L` or `→` | Skip forward 5 seconds |
| `↑` | Jump to previous subtitle segment |
| `↓` | Jump to next subtitle segment |
| `Ctrl + F` | Focus transcript search bar |
| `Esc` | Blur input / Close search |

---

## 📁 Project Structure

```
LocalTranscriptorRomanUrdu/
├── scripts/
│   ├── studio_web.py          # Multithreaded HTTP & SSE Desktop Backend
│   ├── transcribe_pipeline.py # Optimized Faster-Whisper pipeline & VAD
│   ├── roman_urdu.py          # Morphological Urdu-to-Roman transliteration
│   ├── cleanup.py             # Hallucination pruning & phonetic cleanup
│   ├── cuda_helper.py         # Hardware detection (CUDA, cuDNN, CPU)
│   ├── download_models.py     # Local model downloader
│   └── ui.py                  # Fallback legacy GUI
├── ui_web/
│   └── index.html             # MacWhisper 3-column HTML5/Tailwind UI
├── input/                     # Local media staging (.gitkeep)
├── output/                    # Generated transcripts (.gitkeep)
├── models/                    # Cached Faster-Whisper weights (.gitkeep)
├── Dockerfile                 # GPU-accelerated Docker definition
├── docker-compose.yml         # Container orchestrator
├── run_studio_web.bat         # 1-Click Windows launcher
└── requirements.txt           # Python package requirements
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

