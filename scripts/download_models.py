#!/usr/bin/env python3
"""
Model Pre-Downloader for Local Speech Studio
============================================
Pre-downloads Whisper Large-v3 Full (1550M), Whisper Large-v3-Turbo (809M),
and Urdu Sukhan models directly into the local `models/` directory so the
application runs 100% self-contained and offline.
"""

import os
import sys
import argparse
from pathlib import Path

# Ensure scripts directory is on path
_SCRIPTS_DIR = Path(__file__).resolve().parent
_APP_ROOT = _SCRIPTS_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Repository mapping on HuggingFace Hub
MODEL_REPOS = {
    "large-v3": ("Systran/faster-whisper-large-v3", "Whisper Large-v3 Full (High Accuracy • 1550M • Recommended for GPU)", "~3.1 GB"),
    "large-v3-turbo": ("mobiuslabsgmbh/faster-whisper-large-v3-turbo", "Whisper Large-v3-Turbo (Fast & Accurate • 809M)", "~1.6 GB"),
    "urdu-sukhan": ("Loudness-ai/urdu-sukhan-asr-v1", "Urdu Sukhan ASR v1 (Fine-tuned Urdu model)", "~1.2 GB"),
}


def get_default_models_dir() -> Path:
    """Returns local models directory in project root."""
    models_dir = _APP_ROOT / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def download_model_to_dir(model_key: str, models_dir: Path) -> bool:
    """Downloads model weights to the target models directory with progress."""
    if model_key not in MODEL_REPOS:
        print(f"[ERROR] Unknown model key: {model_key}")
        return False

    repo_id, title, est_size = MODEL_REPOS[model_key]
    print("\n" + "=" * 65)
    print(f"  DOWNLOADING: {title}")
    print(f"  Repo:        {repo_id}")
    print(f"  Size:        {est_size}")
    print(f"  Destination: {models_dir}")
    print("=" * 65)
    print("Connecting to Hugging Face Hub... (Progress will be shown below)\n")

    try:
        from huggingface_hub import snapshot_download

        # Allow standard pattern files for CTranslate2 / Transformers
        allow_patterns = [
            "config.json",
            "preprocessor_config.json",
            "model.bin",
            "model.safetensors",
            "tokenizer.json",
            "vocabulary.*",
            "special_tokens_map.json",
            "tokenizer_config.json",
            "generation_config.json",
            "added_tokens.json",
        ]

        target_path = snapshot_download(
            repo_id=repo_id,
            cache_dir=str(models_dir),
            allow_patterns=allow_patterns,
            local_dir_use_symlinks=False,
        )

        print("\n" + "-" * 65)
        print(f"[SUCCESS] Download completed successfully!")
        print(f"  Stored at: {target_path}")
        print("  The model is now ready for 100% offline GPU/CPU inference.")
        print("-" * 65)
        return True

    except Exception as exc:
        print(f"\n[ERROR] Download failed: {exc}")
        print("Please check your internet connection or try again.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download ASR models for Local Speech Studio")
    parser.add_argument(
        "--model",
        choices=["large-v3", "large-v3-turbo", "urdu-sukhan", "all"],
        help="Model to download non-interactively"
    )
    parser.add_argument(
        "--models-dir",
        type=str,
        default=None,
        help="Target directory for downloaded models (default: <app_root>/models)"
    )
    args = parser.parse_args()

    models_dir = Path(args.models_dir).resolve() if args.models_dir else get_default_models_dir()
    models_dir.mkdir(parents=True, exist_ok=True)

    if args.model:
        choice = args.model
        if choice in ("large-v3", "all"):
            download_model_to_dir("large-v3", models_dir)
        if choice in ("large-v3-turbo", "all"):
            download_model_to_dir("large-v3-turbo", models_dir)
        if choice in ("urdu-sukhan", "all"):
            download_model_to_dir("urdu-sukhan", models_dir)
        return

    # Interactive CLI Menu
    print("=" * 65)
    print("       LOCAL SPEECH STUDIO - MODEL PRE-DOWNLOADER")
    print(f"  Target Storage: {models_dir}")
    print("=" * 65)
    print("Choose which model to download for offline testing:")
    print("  [1] Whisper Large-v3 Full  (1550M • ~3.1 GB - Best accuracy, recommended for GPU)")
    print("  [2] Whisper Large-v3-Turbo (809M  • ~1.6 GB - Ultra-fast & high accuracy)")
    print("  [3] Urdu Sukhan ASR v1     (~1.2 GB - Fine-tuned Urdu poetry/conversational)")
    print("  [4] Download ALL Models    (Complete offline suite • ~5.9 GB)")
    print("  [Q] Quit")
    print("=" * 65)

    try:
        sel = input("Enter choice [1-4 or Q] (default=1): ").strip().upper() or "1"
    except (EOFError, KeyboardInterrupt):
        sel = "Q"

    if sel == "1":
        download_model_to_dir("large-v3", models_dir)
    elif sel == "2":
        download_model_to_dir("large-v3-turbo", models_dir)
    elif sel == "3":
        download_model_to_dir("urdu-sukhan", models_dir)
    elif sel == "4":
        print("\nDownloading all models...")
        download_model_to_dir("large-v3", models_dir)
        download_model_to_dir("large-v3-turbo", models_dir)
        download_model_to_dir("urdu-sukhan", models_dir)
    elif sel == "Q":
        print("Cancelled.")
    else:
        print("Invalid selection.")


if __name__ == "__main__":
    main()


