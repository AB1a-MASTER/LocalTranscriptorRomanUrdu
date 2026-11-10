#!/usr/bin/env python3
"""
Stable Local Speech-to-Text Pipeline
=====================================
Transcribes speech from audio or video files. Runs fully locally.

Model  : Whisper Large-v3-Turbo  (CPU · int8 · locked)

Language modes (--language flag):
  ur      Urdu+English mixed (default) — outputs 4 files:
            {stem}.txt, {stem}.srt              (Urdu script)
            {stem}_roman.txt, {stem}_roman.srt  (Roman Urdu)
  en      Pure English — outputs 2 files:
            {stem}.txt, {stem}.srt
  auto    Let Whisper detect — outputs 2 or 4 files depending on result
  <code>  Any Whisper language code (e.g. ar, fr, hi …) — outputs 2 files

Usage:
    python scripts/transcribe_pipeline.py input/lecture.mp4
    python scripts/transcribe_pipeline.py input/talk.mp3 --language en
    python scripts/transcribe_pipeline.py input/ --language auto
    python scripts/transcribe_pipeline.py input/a.mp4 input/b.mp3
    python scripts/transcribe_pipeline.py input/a.mp4 --out D:/my_output
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

# Ensure scripts/ is on the path so roman_urdu can be imported
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import cuda_helper
cuda_helper.init_cuda_dlls()

# ── project root (one level above scripts/) ───────────────────────────────
ROOT       = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

# ── model config ─────────────────────────────────────────────────────────────
MODEL_NAME   = "large-v3-turbo"
TASK         = "transcribe"   # never "translate"
BEAM_SIZE    = 1              # Greedy search with temperature fallback: 3x-5x faster, zero beam loops
CPU_THREADS  = 8
COMPUTE_TYPE = "int8"
VAD_FILTER   = True           # Silero VAD: filters silence and ambient hiss, stops hallucinations
COND_PREV    = False
WORD_TS      = False          # Decoupled: fast sentence-level for UI; computed on-demand for word-SRT

# Per-language initial prompts
_PROMPTS = {
    "ur": (
        "یہ پاکستانی اردو اور انگلش کی ملی جلی گفتگو ہے۔ "
        "SKANS, ACCA, AFM, exam hack, paper, campus, fee, join, link, session, sir, "
        "financial management, lecture, formula sheet, calculations, pass, questions جیسے الفاظ انگلش میں رہیں۔"
    ),
    "en": None,   # no prompt needed for pure English
}

# ── supported formats ─────────────────────────────────────────────────────
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".opus", ".wma"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".m4v",
             ".ts",  ".mts", ".m2ts", ".3gp"}
ALL_EXT   = AUDIO_EXT | VIDEO_EXT


# ── helpers ───────────────────────────────────────────────────────────────

def check_ffmpeg():
    if shutil.which("ffmpeg") is None:
        sys.exit(
            "ERROR: ffmpeg not found on PATH.\n"
            "Download from https://ffmpeg.org/download.html and add to PATH."
        )


def srt_time(seconds: float) -> str:
    """Convert seconds (float) → SRT timestamp string  HH:MM:SS,mmm"""
    ms = round((seconds % 1) * 1000)
    s  = int(seconds)      % 60
    m  = int(seconds) // 60 % 60
    h  = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def extract_audio(src: Path, dst_wav: Path):
    """
    Use ffmpeg to convert any audio or video file to:
      16 kHz · mono · 16-bit PCM WAV  (what Whisper expects)
    """
    ffmpeg_bin = cuda_helper.get_ffmpeg_binary()
    cmd = [
        ffmpeg_bin, "-y",
        "-vn",            # Skip video streams for maximum speed on camera footage
        "-i",  str(src),
        "-ar", "16000",   # sample rate Whisper requires
        "-ac", "1",       # mono
        "-c:a", "pcm_s16le",
        str(dst_wav),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed for: {src}\n"
            f"{result.stderr[-3000:]}"
        )


class SegmentShim:
    def __init__(self, id, start, end, text, words=None, avg_logprob=0.0, no_speech_prob=0.0):
        self.id = id
        self.start = start
        self.end = end
        self.text = text
        self.words = words or []
        self.avg_logprob = avg_logprob
        self.no_speech_prob = no_speech_prob


class WordShim:
    def __init__(self, start, end, word, probability=1.0):
        self.start = start
        self.end = end
        self.word = word
        self.probability = probability


class InfoShim:
    def __init__(self, language="ur", language_probability=1.0, duration=0.0):
        self.language = language
        self.language_probability = language_probability
        self.duration = duration


class TransformersASRWrapper:
    def __init__(self, pipe, model_id: str, device: str = "cpu"):
        self.pipeline = pipe
        self.model_id = model_id
        self.device = device
        self.is_transformers = True

    def transcribe(self, wav_path: Path, language: str = "ur", initial_prompt: str = None):
        gen_kwargs = {}
        if language and language != "auto":
            gen_kwargs["language"] = language
            gen_kwargs["task"] = "transcribe"

        result = self.pipeline(
            str(wav_path),
            return_timestamps="word",
            generate_kwargs=gen_kwargs
        )

        raw_text = result.get("text", "").strip()
        chunks = result.get("chunks", [])

        # Build WordShim list
        all_words = []
        for c in chunks:
            ts = c.get("timestamp") or (0.0, 0.0)
            w_start = ts[0] if ts[0] is not None else (all_words[-1].end if all_words else 0.0)
            w_end = ts[1] if ts[1] is not None else w_start + 0.3
            w_text = c.get("text", "").strip()
            if w_text:
                all_words.append(WordShim(start=w_start, end=w_end, word=w_text))

        # Group words into segments (max 10 words or broken on sentence endings)
        segments = []
        if all_words:
            curr_words = []
            curr_start = None
            seg_id = 1
            for w in all_words:
                if curr_start is None:
                    curr_start = w.start
                curr_words.append(w)
                is_sentence_end = bool(re.search(r"[.?!۔؟]\s*$", w.word))
                if len(curr_words) >= 10 or is_sentence_end:
                    s_end = curr_words[-1].end
                    s_text = " ".join(cw.word for cw in curr_words)
                    segments.append(SegmentShim(id=seg_id, start=curr_start, end=s_end, text=s_text, words=list(curr_words)))
                    seg_id += 1
                    curr_words = []
                    curr_start = None
            if curr_words:
                s_end = curr_words[-1].end
                s_text = " ".join(cw.word for cw in curr_words)
                segments.append(SegmentShim(id=seg_id, start=curr_start, end=s_end, text=s_text, words=list(curr_words)))
        else:
            segments.append(SegmentShim(id=1, start=0.0, end=1.0, text=raw_text, words=[]))

        total_dur = all_words[-1].end if all_words else 1.0
        info = InfoShim(language=language if language != "auto" else "ur", duration=total_dur)
        return segments, info


def get_cuda_status() -> dict:
    """
    Safely inspects CUDA support across PyTorch and CTranslate2 without crashing.
    Returns:
        dict: {
            'cuda_available': bool,
            'torch_cuda': bool,
            'ctranslate2_cuda': bool,
            'device_name': str,
            'compute_types_cuda': list,
            'error_message': str,
        }
    """
    status = {
        "cuda_available": False,
        "torch_cuda": False,
        "ctranslate2_cuda": False,
        "device_name": "CPU",
        "compute_types_cuda": [],
        "error_message": "",
    }
    # 1. Check PyTorch CUDA
    try:
        import torch
        if torch.cuda.is_available():
            status["torch_cuda"] = True
            try:
                status["device_name"] = torch.cuda.get_device_name(0)
            except Exception:
                status["device_name"] = "NVIDIA CUDA Device"
    except Exception as e:
        status["error_message"] = f"PyTorch: {e}"

    # 2. Check CTranslate2 CUDA
    try:
        import ctranslate2
        cuda_count = getattr(ctranslate2, "get_cuda_device_count", lambda: 0)()
        if cuda_count > 0:
            types = ctranslate2.get_supported_compute_types("cuda")
            if types:
                status["ctranslate2_cuda"] = True
                status["compute_types_cuda"] = sorted(list(types))
                if status["device_name"] == "CPU" or "NVIDIA GPU" in status["device_name"]:
                    try:
                        res = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True, timeout=2)
                        if res.returncode == 0 and res.stdout.strip():
                            status["device_name"] = res.stdout.strip().split("\n")[0].strip()
                        else:
                            status["device_name"] = f"NVIDIA GPU ({cuda_count} device{'s' if cuda_count > 1 else ''})"
                    except Exception:
                        status["device_name"] = f"NVIDIA GPU ({cuda_count} device{'s' if cuda_count > 1 else ''})"
    except Exception as e:
        if not status["error_message"]:
            status["error_message"] = f"CTranslate2 CUDA: {e}"

    status["cuda_available"] = status["torch_cuda"] or status["ctranslate2_cuda"]
    status["device_index"] = 0 if status["cuda_available"] else "N/A"
    status["resolved_device"] = "cuda" if status["cuda_available"] else "cpu"
    status["compute_type"] = "float16" if "float16" in status["compute_types_cuda"] else ("int8_float16" if status["cuda_available"] else "int8")
    return status


def resolve_device(device_pref: str = "auto", compute_type: str = None) -> tuple[str, str, dict]:
    """
    Resolves execution device ('cuda' or 'cpu') and compute_type based on preference and hardware.
    Returns: (resolved_device, resolved_compute, cuda_status)
    """
    cuda_status = get_cuda_status()
    pref = (device_pref or "auto").strip().lower()

    if pref in ("cuda", "gpu"):
        resolved_device = "cuda"
        if compute_type:
            resolved_compute = compute_type
        elif "float16" in cuda_status["compute_types_cuda"]:
            resolved_compute = "float16"
        elif "int8_float16" in cuda_status["compute_types_cuda"]:
            resolved_compute = "int8_float16"
        else:
            resolved_compute = "float16"
    elif pref == "cpu":
        resolved_device = "cpu"
        resolved_compute = compute_type or COMPUTE_TYPE
    else:  # "auto"
        if cuda_status["ctranslate2_cuda"] or cuda_status["torch_cuda"]:
            resolved_device = "cuda"
            resolved_compute = compute_type or ("float16" if "float16" in cuda_status["compute_types_cuda"] else "int8_float16")
        else:
            resolved_device = "cpu"
            resolved_compute = compute_type or COMPUTE_TYPE

    return resolved_device, resolved_compute, cuda_status


def _resolve_model_download_root(model_id: str) -> Optional[str]:
    """
    Resolves the directory containing the model or where it should be downloaded.
    Prioritizes:
    1. app_root / 'models'
    2. app_root / 'models' / 'hub'
    3. app_root / 'cache' / 'huggingface' / 'hub'
    4. HF_HOME environment variable
    """
    app_root = Path(__file__).resolve().parent.parent
    candidates = [
        app_root / "models",
        app_root / "models" / "hub",
        app_root / "cache" / "huggingface" / "hub",
    ]
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        candidates.append(Path(hf_home))
        candidates.append(Path(hf_home) / "hub")

    # Check if model is already stored in one of the candidate paths
    for p in candidates:
        if p.is_dir():
            if model_id == "large-v3":
                matches = [m for m in p.glob("*large-v3*") if "turbo" not in m.name.lower()]
            elif model_id == "large-v3-turbo":
                matches = [m for m in p.glob("*large-v3-turbo*")]
            else:
                matches = list(p.glob(f"*{model_id}*"))
            if matches:
                return str(p)

    # If not yet downloaded, prefer local 'models' folder if it exists
    local_models = app_root / "models"
    if local_models.is_dir():
        return str(local_models)

    if hf_home and Path(hf_home).is_dir():
        return str(hf_home)

    return None


def load_model(model_name: str = "large-v3-turbo", device: str = "auto", compute_type: str = None):
    """Load specified ASR model with device & precision selection. Downloads on first run, cached after."""
    resolved_device, resolved_compute, cuda_info = resolve_device(device, compute_type)

    if "urdu-sukhan-asr-v1" in model_name:
        hf_repo = "Loudness-ai/urdu-sukhan-asr-v1"
        print(f"  Loading {hf_repo} (requested device: {device}) …", flush=True)

        import socket
        is_online = False
        try:
            socket.create_connection(("huggingface.co", 443), timeout=0.5)
            is_online = True
        except OSError:
            os.environ["HF_HUB_OFFLINE"] = "1"
            try:
                import huggingface_hub.constants
                huggingface_hub.constants.HF_HUB_OFFLINE = True
            except Exception:
                pass

        hf_token = os.environ.get("HF_TOKEN") or None
        if not hf_token:
            try:
                from huggingface_hub import get_token
                hf_token = get_token()
            except Exception:
                pass

        try:
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
            import torch

            model_dtype = torch.float16 if (resolved_device == "cuda" and cuda_info["torch_cuda"]) else torch.float32
            pipe_dev = 0 if (resolved_device == "cuda" and cuda_info["torch_cuda"]) else "cpu"

            hf_model = AutoModelForSpeechSeq2Seq.from_pretrained(
                hf_repo,
                torch_dtype=model_dtype,
                token=hf_token,
                local_files_only=not is_online
            )
            hf_processor = AutoProcessor.from_pretrained(
                hf_repo,
                token=hf_token,
                local_files_only=not is_online
            )
            pipe = pipeline(
                "automatic-speech-recognition",
                model=hf_model,
                tokenizer=hf_processor.tokenizer,
                feature_extractor=hf_processor.feature_extractor,
                device=pipe_dev
            )
            return TransformersASRWrapper(pipe, hf_repo, device="cuda" if pipe_dev == 0 else "cpu")

        except Exception as pipe_exc:
            err_str = str(pipe_exc)
            if "401" in err_str or "403" in err_str or "gated" in err_str.lower():
                raise RuntimeError(
                    f"Authentication required for {hf_repo}.\n\n"
                    f"This is a gated repository. Please log in with:\n"
                    f"  huggingface-cli login\n"
                    f"or set your HF_TOKEN environment variable."
                ) from pipe_exc
            raise
    else:
        # Determine faster-whisper model identifier
        is_large_v3_full = ("large-v3" in model_name.lower() and "turbo" not in model_name.lower())
        fw_model_id = "large-v3" if is_large_v3_full else ("large-v3-turbo" if "turbo" in model_name.lower() else model_name)
        fw_display = "Whisper Large-v3 (Full 1550M)" if is_large_v3_full else ("Whisper Large-v3-Turbo (809M)" if fw_model_id == "large-v3-turbo" else fw_model_id)

        from faster_whisper import WhisperModel

        download_root = _resolve_model_download_root(fw_model_id)
        model_kwargs = {}
        if download_root:
            model_kwargs["download_root"] = download_root

        if resolved_device == "cuda":
            print(f"  Loading {fw_display} (faster-whisper CUDA · {resolved_compute}) …", flush=True)
            try:
                return WhisperModel(
                    fw_model_id,
                    device="cuda",
                    compute_type=resolved_compute,
                    **model_kwargs,
                )
            except Exception as exc:
                print(f"  [WARNING] CUDA failed to initialize ({exc}). Falling back to CPU mode ({COMPUTE_TYPE} · {CPU_THREADS} threads)...", flush=True)
                return WhisperModel(
                    fw_model_id,
                    device="cpu",
                    compute_type=COMPUTE_TYPE,
                    cpu_threads=CPU_THREADS,
                    **model_kwargs,
                )
        else:
            print(f"  Loading {fw_display} (faster-whisper CPU · {resolved_compute} · {CPU_THREADS} threads) …", flush=True)
            return WhisperModel(
                fw_model_id,
                device="cpu",
                compute_type=resolved_compute,
                cpu_threads=CPU_THREADS,
                **model_kwargs,
            )


def run_transcription(
    model,
    wav: Path,
    language: str = "ur",
    beam_size: Optional[int] = None,
    vad_filter: Optional[bool] = None,
    word_timestamps: Optional[bool] = None,
    progress_callback: Optional[Any] = None,
):
    """
    Run Whisper or Transformers model on a WAV file.
    Supports real-time progress callbacks and streaming segments.
    Returns (segments, info).
    """
    import time

    if getattr(model, "is_transformers", False):
        return model.transcribe(wav, language=language)

    b_size = BEAM_SIZE if beam_size is None else beam_size
    v_filter = VAD_FILTER if vad_filter is None else vad_filter
    w_ts = WORD_TS if word_timestamps is None else word_timestamps

    if language == "auto":
        from faster_whisper import decode_audio
        audio = decode_audio(str(wav), sampling_rate=16000)
        detected_lang, prob, _ = model.detect_language(audio)
        # In Pakistani context, speech classified as Hindi or Urdu is routed to
        # Urdu ('ur') with bilingual prompt to ensure Urdu script + Roman Urdu output.
        if detected_lang in ("ur", "hi"):
            target_lang = "ur"
            prompt = _PROMPTS["ur"]
        else:
            target_lang = detected_lang
            prompt = _PROMPTS.get(target_lang)
    else:
        target_lang = language
        prompt = _PROMPTS.get(language)

    vad_params = dict(min_silence_duration_ms=500, speech_pad_ms=200) if v_filter else None

    segments_gen, info = model.transcribe(
        str(wav),
        language=target_lang,
        task=TASK,
        beam_size=b_size,
        vad_filter=v_filter,
        vad_parameters=vad_params,
        condition_on_previous_text=COND_PREV,
        word_timestamps=w_ts,
        initial_prompt=prompt,
        temperature=[0.0, 0.2, 0.4],
    )

    total_dur = getattr(info, "duration", 0.0) or 1.0
    start_wall = time.time()
    collected_segments = []

    for seg in segments_gen:
        collected_segments.append(seg)
        if progress_callback:
            elapsed_wall = max(0.001, time.time() - start_wall)
            curr_sec = seg.end
            progress_pct = min(100.0, (curr_sec / total_dur) * 100.0)
            speed_factor = curr_sec / elapsed_wall if elapsed_wall > 0 else 1.0
            eta_sec = max(0.0, (total_dur - curr_sec) / speed_factor) if speed_factor > 0 else 0.0
            try:
                progress_callback({
                    "segment": seg,
                    "text": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                    "current_time": curr_sec,
                    "total_duration": total_dur,
                    "progress_pct": progress_pct,
                    "speed_factor": speed_factor,
                    "eta_seconds": eta_sec,
                })
            except Exception:
                pass

    return collected_segments, info


# ── output writers ────────────────────────────────────────────────────────

def write_plain_text(segments, path: Path):
    """Plain text — one block, no timestamps, with conservative cleanup."""
    from cleanup import clean_urdu_text
    text = " ".join(s.text.strip() for s in segments).strip()
    cleaned = clean_urdu_text(text)
    path.write_text(cleaned + "\n", encoding="utf-8")


def write_srt(segments, path: Path):
    """
    Word-level SRT — one subtitle entry per word.

    Each word gets its own timestamp so the file can be used for:
      • Auto-editors (DaVinci Resolve, Premiere, auto-editor)
      • Karaoke-style subtitles
      • Manual timing correction at word granularity

    Falls back to segment-level entries for any segment that has no
    word-level data (should not happen with word_timestamps=True).
    """
    entries = []
    idx = 1

    for seg in segments:
        words = seg.words or []

        if words:
            for w in words:
                word_text = w.word.strip()
                if not word_text:
                    continue
                entries.append(
                    f"{idx}\n"
                    f"{srt_time(w.start)} --> {srt_time(w.end)}\n"
                    f"{word_text}\n"
                )
                idx += 1
        else:
            # Segment-level fallback
            text = seg.text.strip()
            if text:
                entries.append(
                    f"{idx}\n"
                    f"{srt_time(seg.start)} --> {srt_time(seg.end)}\n"
                    f"{text}\n"
                )
                idx += 1

    path.write_text("\n".join(entries), encoding="utf-8")


# ── per-file processing ───────────────────────────────────────────────────

def process_file(src: Path, out_dir: Path, model, language: str = "ur") -> bool:
    """
    Transcribe one file. Returns True on success, False on error.

    language="ur"   → 4 outputs: Urdu script txt+srt + Roman Urdu txt+srt
    language="en"   → 2 outputs: English txt+srt only
    language="auto" → Whisper detects; Roman Urdu outputs added if ur detected
    language=other  → 2 outputs: txt+srt in detected language
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    stem     = src.stem
    txt_path = out_dir / f"{stem}.txt"
    srt_path = out_dir / f"{stem}.srt"

    print(f"\n{'-' * 62}")
    print(f"  Input    : {src.name}")
    print(f"  Type     : {'video' if src.suffix.lower() in VIDEO_EXT else 'audio'}")
    print(f"  Language : {language if language != 'auto' else 'auto-detect'}")

    try:
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "audio.wav"

            # Always run through ffmpeg — normalises sample rate and format
            print("  Extracting / converting audio via ffmpeg …", flush=True)
            extract_audio(src, wav)

            print("  Transcribing …", flush=True)
            raw_segments, info = run_transcription(model, wav, language=language)
            # ↑ segments list is built before 'with' block exits, so the
            #   temp WAV is still alive while Whisper reads it.

        # ── Priority 4: Conservative cleanup (dedup loops, remove silence outro) ─
        from cleanup import clean_segments, clean_roman_text, clean_roman_text_in_srt
        segments = clean_segments(raw_segments)

        # Write outputs (outside temp dir — WAV already in memory as segments)
        write_plain_text(segments, txt_path)
        write_srt(segments, srt_path)

        # ── Roman Urdu outputs (only when processing Urdu speech) ─────────────
        is_urdu = (info.language == "ur") or (language == "ur")
        if is_urdu:
            from roman_urdu import transliterate, transliterate_srt
            plain_text = txt_path.read_text(encoding='utf-8')
            roman_txt_path = out_dir / f"{stem}_roman.txt"
            roman_srt_path = out_dir / f"{stem}_roman.srt"

            # Transliterate and apply Roman Urdu cleanup (e.g. 'base kay uper')
            roman_clean = clean_roman_text(transliterate(plain_text))
            roman_txt_path.write_text(roman_clean + "\n", encoding='utf-8')

            # Subtitle cleanup for Roman SRT
            raw_roman_srt = transliterate_srt(srt_path.read_text(encoding='utf-8'))
            roman_srt_path.write_text(
                clean_roman_text_in_srt(raw_roman_srt),
                encoding='utf-8'
            )

        word_count = sum(len(s.words) for s in segments if s.words)
        print(f"  Language detected : {info.language} "
              f"(confidence {info.language_probability:.2f})")
        print(f"  Words timestamped : {word_count}")
        if is_urdu:
            print(f"  [Urdu script] plain → {txt_path}")
            print(f"  [Urdu script] SRT   → {srt_path}")
            print(f"  [Roman Urdu ] plain → {roman_txt_path}")
            print(f"  [Roman Urdu ] SRT   → {roman_srt_path}")
        else:
            print(f"  [Plain text ] → {txt_path}")
            print(f"  [SRT file   ] → {srt_path}")
        return True

    except Exception as exc:
        print(f"\n  ERROR: {exc}", file=sys.stderr)
        return False


# ── CLI ───────────────────────────────────────────────────────────────────

def collect_files(inputs: list[str]) -> list[Path]:
    """Expand files and directories into a flat list of supported paths."""
    files = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            found = sorted(f for f in p.iterdir()
                           if f.is_file() and f.suffix.lower() in ALL_EXT)
            if not found:
                print(f"  WARNING: No supported files found in: {p}")
            files.extend(found)
        elif p.is_file():
            if p.suffix.lower() not in ALL_EXT:
                print(f"  WARNING: Unsupported format, skipping: {p}")
            else:
                files.append(p)
        else:
            sys.exit(f"ERROR: Path not found: {p}")
    return files


def main():
    # Force UTF-8 stdout on Windows so any Unicode in filenames/text prints cleanly
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(
        description="Local Urdu-English speech-to-text (audio + video).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "input", nargs="+",
        help="Audio/video file(s) or folder(s) to transcribe.",
    )
    ap.add_argument(
        "--out", metavar="DIR", default=str(OUTPUT_DIR),
        help=f"Output directory. Default: {OUTPUT_DIR}",
    )
    ap.add_argument(
        "--language", "-l", default="ur",
        help="Language mode: 'ur' (Urdu/English mixed, generates Roman Urdu too; default), 'en' (pure English), 'auto' (detect language), or any Whisper language code.",
    )
    ap.add_argument(
        "--model", "-m", default="large-v3-turbo",
        help="ASR Model: 'large-v3-turbo' (default), 'large-v3' (high-accuracy 1550M), or 'Loudness-ai/urdu-sukhan-asr-v1'.",
    )
    ap.add_argument(
        "--device", "-d", default="auto", choices=["auto", "cuda", "cpu"],
        help="Compute device: 'auto' (detect CUDA if available, else CPU; default), 'cuda' (GPU), or 'cpu'.",
    )
    ap.add_argument(
        "--compute-type", default=None,
        help="Quantization / compute type: e.g. 'float16', 'int8_float16', 'int8', 'float32'. (Default: auto-selected by device).",
    )
    args = ap.parse_args()

    check_ffmpeg()

    files = collect_files(args.input)
    if not files:
        sys.exit("No supported files found — nothing to do.")

    out_dir = Path(args.out)

    print(f"\nSpeech-to-Text Transcription Pipeline")
    print(f"Model  : {args.model}  |  Device : {args.device}  |  Language : {args.language}  |  Task : {TASK}")
    print(f"Output : {out_dir}")
    print(f"\nFiles to process ({len(files)}):")
    for f in files:
        tag = "VIDEO" if f.suffix.lower() in VIDEO_EXT else "AUDIO"
        print(f"  [{tag}] {f}")

    # Load model once, reuse for all files
    model = load_model(args.model, device=args.device, compute_type=args.compute_type)

    ok, failed = 0, 0
    for f in files:
        if process_file(f, out_dir, model, language=args.language):
            ok += 1
        else:
            failed += 1

    print(f"\n{'=' * 62}")
    print(f"Finished.  OK: {ok}   Failed: {failed}")
    print(f"Outputs in: {out_dir}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

