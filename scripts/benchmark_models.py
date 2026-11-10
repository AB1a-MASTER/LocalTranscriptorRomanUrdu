#!/usr/bin/env python3
"""
benchmark_models.py
===================
Comparative Model Benchmark Evaluation:
  - Whisper Large-v3-Turbo (Faster-Whisper)
  - Loudness-ai/urdu-sukhan-asr-v1 (Hugging Face Transformers)

Evaluates on reference files in input/:
  - test.wav (19.4s)
  - test2.mp3 (57.5s)
  - test3english.mp4 (23.8s)
"""

import sys
import os
import time
import json
import gc
import tempfile
from pathlib import Path

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import socket
try:
    socket.create_connection(("huggingface.co", 443), timeout=0.5)
except OSError:
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        import huggingface_hub.constants
        huggingface_hub.constants.HF_HUB_OFFLINE = True
    except Exception:
        pass

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import transcribe_pipeline as tp
import cleanup
import roman_urdu

ROOT_DIR = _SCRIPTS_DIR.parent
INPUT_DIR = ROOT_DIR / "input"

FILES = [
    ("test.wav", "ur"),
    ("test2.mp3", "ur"),
    ("test3english.mp4", "auto"),
]

MODELS = [
    ("Whisper Large-v3-Turbo", "large-v3-turbo"),
    ("Urdu Sukhan ASR v1", "Loudness-ai/urdu-sukhan-asr-v1"),
]


def run_benchmark():
    print("=" * 80)
    print("  URDU-ENGLISH SPEECH-TO-TEXT: COMPARATIVE MODEL BENCHMARK EVALUATION")
    print("=" * 80)
    print(f"Platform: Windows | Python: {sys.version.split()[0]}")
    cuda_stat = tp.get_cuda_status()
    print(f"Hardware: {cuda_stat['device_name']} (CUDA: {cuda_stat['cuda_available']})")
    print(f"CPU Threads Allocated: {tp.CPU_THREADS}")
    print("-" * 80)

    # Extract audio for all input files once
    extracted_wavs = {}
    durations = {}
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for fname, _ in FILES:
            src = INPUT_DIR / fname
            if not src.exists():
                print(f"Warning: File {src} not found! Skipping.")
                continue
            wav_dst = tmp_path / f"{src.stem}.wav"
            tp.extract_audio(src, wav_dst)
            extracted_wavs[fname] = wav_dst.read_bytes()  # keep in memory
            # get duration
            try:
                import subprocess
                cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(src)]
                info = json.loads(subprocess.check_output(cmd))
                durations[fname] = float(info["format"]["duration"])
            except Exception:
                durations[fname] = 0.0

        results = {}

        for display_name, model_key in MODELS:
            print(f"\n[{display_name}]")
            print(f"  Loading model into memory...")
            t0 = time.time()
            model = tp.load_model(model_key, device="auto")
            load_time = time.time() - t0
            print(f"  Model loaded in {load_time:.2f}s.")

            model_results = {"load_time": load_time, "files": {}}

            for fname, lang in FILES:
                if fname not in extracted_wavs:
                    continue
                wav_file = tmp_path / f"{fname}.wav"
                wav_file.write_bytes(extracted_wavs[fname])
                dur = durations[fname]

                print(f"  --> Transcribing '{fname}' (duration: {dur:.1f}s, lang: {lang})...", end="", flush=True)
                t_inf_start = time.time()
                try:
                    segments, info = tp.run_transcription(model, wav_file, language=lang)
                    inf_time = time.time() - t_inf_start
                    rtf = inf_time / dur if dur > 0 else 0.0
                    print(f" Done in {inf_time:.2f}s (RTF: {rtf:.2f}x).")

                    cleaned_segments = cleanup.clean_segments(segments)
                    raw_urdu = " ".join(s.text.strip() for s in cleaned_segments)
                    clean_urdu = cleanup.clean_urdu_text(raw_urdu)
                    clean_roman = cleanup.clean_roman_text(roman_urdu.transliterate(clean_urdu))

                    model_results["files"][fname] = {
                        "inf_time": inf_time,
                        "rtf": rtf,
                        "duration": dur,
                        "detected_lang": getattr(info, "language", lang),
                        "urdu_text": clean_urdu,
                        "roman_text": clean_roman,
                        "word_count": len(clean_roman.split()),
                        "num_segments": len(cleaned_segments),
                        "success": True,
                    }
                except Exception as exc:
                    inf_time = time.time() - t_inf_start
                    print(f" FAILED after {inf_time:.2f}s ({exc})")
                    model_results["files"][fname] = {
                        "inf_time": inf_time,
                        "error": str(exc),
                        "success": False,
                    }

            results[display_name] = model_results
            del model
            gc.collect()

    # ── Summary Report ────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("  BENCHMARK SUMMARY & COMPARISON")
    print("=" * 80)

    # 1. Timing Comparison Table
    print("\n1. SPEED & LATENCY COMPARISON (CPU · Intel Core i5-12400 · 8 Threads):")
    print(f"{'File':<18} {'Duration':<10} {'Whisper Large-v3-Turbo':<26} {'Urdu Sukhan ASR v1':<26}")
    print("-" * 80)
    for fname, _ in FILES:
        dur_str = f"{durations.get(fname, 0.0):.1f}s"
        w_res = results.get("Whisper Large-v3-Turbo", {}).get("files", {}).get(fname, {})
        s_res = results.get("Urdu Sukhan ASR v1", {}).get("files", {}).get(fname, {})

        w_str = f"{w_res.get('inf_time', 0.0):.2f}s (RTF {w_res.get('rtf', 0.0):.2f}x)" if w_res.get("success") else "FAILED"
        s_str = f"{s_res.get('inf_time', 0.0):.2f}s (RTF {s_res.get('rtf', 0.0):.2f}x)" if s_res.get("success") else "FAILED"
        print(f"{fname:<18} {dur_str:<10} {w_str:<26} {s_str:<26}")

    # 2. Transcripts Side-by-Side
    print("\n" + "=" * 80)
    print("2. TRANSCRIPTION OUTPUT COMPARISON:")
    print("=" * 80)

    for fname, lang in FILES:
        print(f"\n--------------------------------------------------------------------------------")
        print(f"FILE: {fname}  (Duration: {durations.get(fname, 0):.1f}s, Language Mode: {lang})")
        print(f"--------------------------------------------------------------------------------")

        w_res = results.get("Whisper Large-v3-Turbo", {}).get("files", {}).get(fname, {})
        s_res = results.get("Urdu Sukhan ASR v1", {}).get("files", {}).get(fname, {})

        print("\n[Whisper Large-v3-Turbo]:")
        if w_res.get("success"):
            print("  Urdu Script :", w_res.get("urdu_text"))
            print("  Roman Urdu  :", w_res.get("roman_text"))
            print(f"  Stats       : {w_res.get('word_count')} words | {w_res.get('num_segments')} segments | {w_res.get('inf_time'):.2f}s")
        else:
            print("  ERROR:", w_res.get("error"))

        print("\n[Urdu Sukhan ASR v1]:")
        if s_res.get("success"):
            print("  Urdu Script :", s_res.get("urdu_text"))
            print("  Roman Urdu  :", s_res.get("roman_text"))
            print(f"  Stats       : {s_res.get('word_count')} words | {s_res.get('num_segments')} segments | {s_res.get('inf_time'):.2f}s")
        else:
            print("  ERROR:", s_res.get("error"))

    print("\n" + "=" * 80)
    print("  EVALUATION COMPLETE")
    print("=" * 80)

    # Save benchmark JSON for reference
    report_json_path = ROOT_DIR / "output" / "benchmark_evaluation.json"
    report_json_path.parent.mkdir(exist_ok=True, parents=True)
    report_json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRaw benchmark metrics saved to: {report_json_path}")


if __name__ == "__main__":
    run_benchmark()
