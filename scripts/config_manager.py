"""
config_manager.py
=================
Persistent user configuration manager for Local Speech-to-Text Studio.
Saves user preferences (device mode, selected model, language mode, SRT timing style)
to `user_config.json` so choices are remembered across sessions.
"""

import json
from pathlib import Path
from typing import Any, Dict

CONFIG_FILE = Path(__file__).resolve().parent / "user_config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "theme": "light",       # "light" | "dark"
    "device_mode": "auto",  # "auto" | "cuda" | "cpu"
    "model_name": "Whisper Large-v3-Turbo (Faster-Whisper)",
    "language_mode": "Auto-detect (Default)",
    "srt_style": "Word-by-word (1 word/cue)",
    "custom_output_dir": "",
}


def load_config() -> Dict[str, Any]:
    """Load configuration from JSON file. Merges with defaults if keys are missing."""
    cfg = dict(DEFAULT_CONFIG)
    if not CONFIG_FILE.exists():
        return cfg

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            cfg.update(data)
    except Exception as exc:
        print(f"[config_manager] Warning: Failed to read {CONFIG_FILE.name}: {exc}")

    return cfg


def save_config(new_config: Dict[str, Any]) -> bool:
    """Save configuration dictionary to JSON file."""
    try:
        current = load_config()
        current.update(new_config)
        CONFIG_FILE.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception as exc:
        print(f"[config_manager] Error: Failed to save {CONFIG_FILE.name}: {exc}")
        return False


def get_setting(key: str, default: Any = None) -> Any:
    """Get a single setting value."""
    cfg = load_config()
    return cfg.get(key, default if default is not None else DEFAULT_CONFIG.get(key))


def set_setting(key: str, value: Any) -> bool:
    """Set and persist a single setting value."""
    return save_config({key: value})

