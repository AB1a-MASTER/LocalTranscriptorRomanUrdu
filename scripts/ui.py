#!/usr/bin/env python3
"""
Local Speech-to-Text Studio
============================
Native Windows Desktop Application (Tkinter).
Fully local speech-to-text studio for Pakistani Urdu-English mixed speech.
Preserves bilingual code-switching, Roman Urdu 4-tier transliteration,
interactive waveform timeline, synchronized follow-along word highlighting,
text-based selection preview, and surgical word-fixing.
"""

import os
import sys
import shutil
import subprocess
import threading
import tempfile
import time
import difflib
import re
from pathlib import Path
from typing import List, Dict, Optional, Any
import numpy as np

# Ensure Windows High-DPI awareness before Tkinter initializes
try:
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
    except Exception:
        ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Ensure scripts directory is on path
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import cuda_helper
cuda_helper.init_cuda_dlls()

# Import pipeline modules
import roman_urdu
import cleanup
import transcribe_pipeline
import config_manager
from audio_player import AudioPlayer

ROOT_DIR = _SCRIPTS_DIR.parent
OUTPUT_DIR = ROOT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ════════════════════════════════════════════════════════════════════════════
# DESIGN SYSTEM TOKENS (Light & Dark Palettes per UX Specification)
# ════════════════════════════════════════════════════════════════════════════
THEME_TOKENS = {
    "dark": {
        "app_bg": "#111827",
        "primary_surface": "#182235",
        "elevated_surface": "#202D42",
        "editor_surface": "#151F30",
        "border": "#344256",
        "btn_bg": "#202D42",
        "btn_border": "#344256",
        "btn_hover": "#2A3B53",
        "primary_text": "#F3F6FC",
        "secondary_text": "#A7B4C7",
        "muted_text": "#78869B",
        "accent": "#4F8CFF",
        "accent_hover": "#3D78E8",
        "success": "#2FBF83",
        "warning": "#E7A743",
        "error": "#E16B70",
        "active_word_bg": "#854d0e",
        "active_word_fg": "#fef08a",
        "waveform_bg": "#151F30",
        "waveform_wave": "#4F8CFF",
        "waveform_playhead": "#E7A743",
        "select_bg": "#2563eb",
    },
    "light": {
        "app_bg": "#f0f2f5",             # Clean Bootstrap-style neutral background (no stark plain white)
        "primary_surface": "#f8f9fa",    # Bootstrap navbar / header surface
        "elevated_surface": "#ffffff",   # Crisp card container with 1px border
        "editor_surface": "#ffffff",     # Writing canvas
        "border": "#ced4da",             # Bootstrap $border-color - crisp, visible 1px boundary
        "btn_bg": "#f8f9fa",             # Bootstrap light button background
        "btn_border": "#ced4da",         # Distinct button boundary
        "btn_hover": "#e2e6ea",          # Subtle active/hover state
        "primary_text": "#212529",       # Bootstrap dark body color - dark, crisp
        "secondary_text": "#2b3035",     # Deep charcoal - NO washed-out grey
        "muted_text": "#343a40",         # Dark slate - NO washed-out grey
        "accent": "#0d6efd",             # Bootstrap primary blue
        "accent_hover": "#0b5ed7",       # Bootstrap primary hover
        "success": "#198754",            # Bootstrap success green
        "warning": "#d97706",            # Bootstrap warning gold-amber
        "error": "#dc3545",              # Bootstrap danger red
        "active_word_bg": "#fff3cd",     # Bootstrap warning light / warm highlight
        "active_word_fg": "#000000",     # 100% black text for maximum highlight contrast
        "waveform_bg": "#e9ecef",        # Bootstrap light gray timeline
        "waveform_wave": "#0d6efd",      # Bootstrap blue waveform
        "waveform_playhead": "#dc3545",  # Bootstrap danger red playhead cursor
        "select_bg": "#b6d4fe",          # Bootstrap soft blue selection
    }
}

# Cache loaded model instance across sessions
_CACHED_MODEL = None
_CACHED_MODEL_NAME = None
_CACHED_MODEL_DEVICE = None


def format_time(seconds: float) -> str:
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"


def format_playback_time(seconds: float) -> str:
    """Formats seconds into MM:SS.s (or HH:MM:SS.s for long files)."""
    if seconds < 0:
        seconds = 0.0
    total_sec = float(seconds)
    m = int(total_sec) // 60
    s = total_sec % 60
    h = m // 60
    m = m % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:04.1f}"
    return f"{m:02d}:{s:04.1f}"


def parse_srt_time(t_str: str) -> float:
    """Parses 'HH:MM:SS,mmm' or 'HH:MM:SS.mmm' into seconds float."""
    t_str = t_str.replace(",", ".").strip()
    parts = t_str.split(":")
    if len(parts) == 3:
        try:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except Exception:
            return 0.0
    return 0.0


def parse_srt_words(srt_content: str) -> List[dict]:
    """Parses word-level or cue-level SRT subtitle text into list of dicts with word, start, end."""
    pattern = re.compile(
        r'(\d+)\s*\n(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n([^\n\r]+)',
        re.MULTILINE
    )
    items = []
    for m in pattern.finditer(srt_content):
        start = parse_srt_time(m.group(2))
        end = parse_srt_time(m.group(3))
        text = m.group(4).strip()
        items.append({"word": text, "start": start, "end": end})
    return items


def get_file_info(filepath: Path) -> str:
    """Returns a short info string (size, duration if available)."""
    if not filepath.exists():
        return ""
    size_mb = filepath.stat().st_size / (1024 * 1024)
    info = f"{size_mb:.1f} MB"
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            str(filepath)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            dur = float(res.stdout.strip())
            info = f"{format_playback_time(dur)} duration  •  {info}"
    except Exception:
        pass
    return info


def format_srt_cues(timed_words: List[tuple], max_words_per_cue: int = 1) -> str:
    """
    Groups timed_words (word_str, start_sec, end_sec) into SRT subtitle cues.
    - If max_words_per_cue == 1: strict word-by-word (Karaoke/auto-editor style).
    - If max_words_per_cue > 1: groups up to N words, breaking early at sentence endings (. ? ! ۔ ؟).
    """
    if not timed_words:
        return ""

    if max_words_per_cue <= 1:
        entries = []
        for idx, (w, w_start, w_end) in enumerate(timed_words, start=1):
            entries.append(
                f"{idx}\n"
                f"{transcribe_pipeline.srt_time(w_start)} --> {transcribe_pipeline.srt_time(w_end)}\n"
                f"{w}\n"
            )
        return "\n".join(entries)

    cues = []
    current_cue_words = []
    current_start = None
    current_end = None

    for w, w_start, w_end in timed_words:
        if current_start is None:
            current_start = w_start
        current_end = w_end
        current_cue_words.append(w)

        is_sentence_end = bool(re.search(r"[.?!۔؟\n]\s*$", w))
        if len(current_cue_words) >= max_words_per_cue or is_sentence_end:
            cues.append((current_start, current_end, " ".join(current_cue_words)))
            current_cue_words = []
            current_start = None
            current_end = None

    if current_cue_words:
        cues.append((current_start, current_end, " ".join(current_cue_words)))

    entries = []
    for idx, (c_start, c_end, text) in enumerate(cues, start=1):
        entries.append(
            f"{idx}\n"
            f"{transcribe_pipeline.srt_time(c_start)} --> {transcribe_pipeline.srt_time(c_end)}\n"
            f"{text}\n"
        )
    return "\n".join(entries)


# ════════════════════════════════════════════════════════════════════════════
# PREFERENCES DIALOG (Modal)
# ════════════════════════════════════════════════════════════════════════════

class PreferencesDialog(tk.Toplevel):
    def __init__(self, parent, on_saved_callback=None):
        super().__init__(parent)
        self.title("Spelling & Transliteration Preferences")
        self.geometry("580x480")
        self.minsize(480, 360)
        self.transient(parent)
        self.grab_set()

        cur_theme = getattr(parent, "current_theme", "dark")
        tokens = THEME_TOKENS.get(cur_theme, THEME_TOKENS["dark"])
        self.configure(background=tokens["app_bg"])

        self.on_saved = on_saved_callback
        self.preferences = roman_urdu.get_preferences()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_ui(self):
        pad = 12
        frame = ttk.Frame(self, padding=pad)
        frame.pack(fill=tk.BOTH, expand=True)

        lbl = ttk.Label(
            frame,
            text="Spelling Overrides (preferences.json)\n"
                 "Map Urdu or incorrect Roman words to your preferred Roman Urdu spelling.\n"
                 "Overrides take precedence over the built-in dictionary.",
            style="SubHeader.TLabel",
            justify=tk.LEFT
        )
        lbl.pack(anchor=tk.W, pady=(0, 8))

        cols = ("Urdu / Key", "Preferred Roman Urdu")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=10)
        self.tree.heading("Urdu / Key", text="Urdu Word / Key")
        self.tree.heading("Preferred Roman Urdu", text="Preferred Roman Urdu Spelling")
        self.tree.column("Urdu / Key", width=220, anchor=tk.W)
        self.tree.column("Preferred Roman Urdu", width=260, anchor=tk.W)

        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, before=self.tree)

        self._populate_tree()

        # Input fields for add/edit
        f_edit = ttk.LabelFrame(frame, text="Add / Edit Rule", padding=8)
        f_edit.pack(fill=tk.X, pady=(10, 4))

        f_grid = ttk.Frame(f_edit)
        f_grid.pack(fill=tk.X)

        ttk.Label(f_grid, text="Urdu / Key:").grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        self.entry_key = ttk.Entry(f_grid, width=22)
        self.entry_key.grid(row=0, column=1, sticky=tk.W, padx=4, pady=2)

        ttk.Label(f_grid, text="Roman Urdu:").grid(row=0, column=2, sticky=tk.W, padx=4, pady=2)
        self.entry_val = ttk.Entry(f_grid, width=22)
        self.entry_val.grid(row=0, column=3, sticky=tk.W, padx=4, pady=2)

        btn_add = ttk.Button(f_grid, text="Add / Update", command=self._add_rule)
        btn_add.grid(row=0, column=4, padx=6, pady=2)

        btn_del = ttk.Button(f_edit, text="Delete Selected", command=self._delete_selected)
        btn_del.pack(anchor=tk.E, pady=(4, 0))

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Footer actions
        f_foot = ttk.Frame(frame)
        f_foot.pack(fill=tk.X, pady=(8, 0))

        btn_save = ttk.Button(f_foot, text="Save Preferences", style="Primary.TButton", command=self._save_and_close)
        btn_save.pack(side=tk.RIGHT, padx=4)

        btn_close = ttk.Button(f_foot, text="Cancel", command=self.destroy)
        btn_close.pack(side=tk.RIGHT, padx=4)

    def _populate_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for k in sorted(self.preferences.keys()):
            self.tree.insert("", tk.END, values=(k, self.preferences[k]))

    def _on_select(self, event):
        sel = self.tree.selection()
        if sel:
            k, v = self.tree.item(sel[0], "values")
            self.entry_key.delete(0, tk.END)
            self.entry_key.insert(0, k)
            self.entry_val.delete(0, tk.END)
            self.entry_val.insert(0, v)

    def _add_rule(self):
        k = self.entry_key.get().strip()
        v = self.entry_val.get().strip()
        if not k or not v:
            messagebox.showwarning("Input Required", "Both fields are required.", parent=self)
            return
        self.preferences[k] = v
        self._populate_tree()
        self.entry_key.delete(0, tk.END)
        self.entry_val.delete(0, tk.END)

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        k, _ = self.tree.item(sel[0], "values")
        if k in self.preferences:
            del self.preferences[k]
        self._populate_tree()

    def _save_and_close(self):
        roman_urdu.save_preferences(self.preferences)
        if self.on_saved:
            self.on_saved()
        self.destroy()


# ════════════════════════════════════════════════════════════════════════════
# HARDWARE INFO DIALOG (Modal)
# ════════════════════════════════════════════════════════════════════════════

class HardwareInfoDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Hardware & Compute Device Diagnostics")
        self.geometry("540x440")
        self.minsize(460, 340)
        self.transient(parent)
        self.grab_set()

        cur_theme = getattr(parent, "current_theme", "dark")
        tokens = THEME_TOKENS.get(cur_theme, THEME_TOKENS["dark"])
        self.configure(background=tokens["app_bg"])

        self._build_ui(tokens)

    def _build_ui(self, tokens: dict):
        f = ttk.Frame(self, padding=16)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text="Hardware Diagnostics", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 6))

        info_box = tk.Text(
            f,
            wrap=tk.WORD,
            font=("Consolas", 9),
            padx=10,
            pady=10,
            relief="flat",
            bd=1,
            bg=tokens["editor_surface"],
            fg=tokens["primary_text"],
            insertbackground=tokens["primary_text"],
            highlightbackground=tokens["border"],
            highlightthickness=1
        )
        info_box.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        status = transcribe_pipeline.get_cuda_status()
        import platform
        cpu_count = os.cpu_count() or 8
        proc_name = platform.processor() or "Multi-Core CPU"
        ffmpeg_bin = transcribe_pipeline.cuda_helper.get_ffmpeg_binary()
        ffmpeg_ok = "Found" if (ffmpeg_bin and (ffmpeg_bin != "ffmpeg" or shutil.which("ffmpeg"))) else "NOT FOUND"

        lines = [
            "============================================================",
            " LOCAL COMPUTE DEVICE STATUS",
            "============================================================",
            f"PyTorch CUDA Available:     {status.get('cuda_available', False)}",
            f"Active CUDA Device:         {status.get('device_name', 'None')}",
            f"Active Device Index:        {status.get('device_index', 'N/A')}",
            f"CTranslate2 CUDA Supported: {status.get('ctranslate2_cuda', False)}",
            f"Resolved Device Engine:     {status.get('resolved_device', 'cpu')}",
            f"Recommended Compute Type:   {status.get('compute_type', 'int8')}",
            "",
            "------------------------------------------------------------",
            " HARDWARE RUNTIME DETAILS",
            "------------------------------------------------------------",
            f"CPU Logical Cores:          {cpu_count} cores ({proc_name})",
            f"Python Runtime:             {sys.version.split()[0]} ({sys.platform})",
            f"Whisper Acceleration:       int8 CPU / float16 CUDA",
            f"VAD Filtering:              False (Preserves Urdu word boundaries)",
            f"FFmpeg Binary:              {ffmpeg_bin} [{ffmpeg_ok}]",
            "",
            "------------------------------------------------------------",
            " ACCELERATION MODES",
            "------------------------------------------------------------",
            " • Auto: Uses CUDA if an NVIDIA GPU with drivers is present;",
            "         falls back gracefully to multi-threaded CPU int8.",
            " • GPU:  Forces CUDA acceleration (requires NVIDIA drivers).",
            " • CPU:  Forces 8-threaded CPU int8 inference for stable local run.",
            "============================================================"
        ]

        info_box.insert(tk.END, "\n".join(lines))
        info_box.config(state=tk.DISABLED)

        btn_close = ttk.Button(f, text="Close", command=self.destroy)
        btn_close.pack(anchor=tk.E)


# ════════════════════════════════════════════════════════════════════════════
# SURGICAL WORD FIXING DIALOG (Modal)
# ════════════════════════════════════════════════════════════════════════════

class WordFixDialog(tk.Toplevel):
    """
    Contextual word correction dialog supporting:
      1. Single-instance surgical word fix (replaces ONLY the selected instance)
      2. Document-wide replacement (replaces ALL occurrences in the active tab)
      3. Save to Library (preferences.json for all future transcriptions)
    """
    def __init__(self, parent, initial_word: str = "", is_urdu_tab: bool = False,
                 has_selection: bool = False, selection_range: tuple = None,
                 context_snippet: str = "", on_fixed_callback=None):
        super().__init__(parent)
        self.title("Fix Spoken Word")
        self.geometry("540x440")
        self.minsize(480, 380)
        self.transient(parent)
        self.grab_set()

        self.initial_word = initial_word.strip()
        self.is_urdu_tab = is_urdu_tab
        self.has_selection = has_selection
        self.selection_range = selection_range
        self.context_snippet = context_snippet
        self.on_fixed = on_fixed_callback

        cur_theme = getattr(parent, "current_theme", "dark")
        tokens = THEME_TOKENS.get(cur_theme, THEME_TOKENS["dark"])
        self.configure(background=tokens["app_bg"])

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_ui(self):
        f = ttk.Frame(self, padding=16)
        f.pack(fill=tk.BOTH, expand=True)

        tab_type = "Urdu Script" if self.is_urdu_tab else "Roman Urdu"
        ttk.Label(
            f,
            text=f"Correct Word in {tab_type}",
            style="Header.TLabel"
        ).pack(anchor=tk.W, pady=(0, 4))

        ttk.Label(
            f,
            text="Correct a misrecognized word. You can replace just this single occurrence,\n"
                 "update all matching words across the document, or save it permanently.",
            style="SubHeader.TLabel"
        ).pack(anchor=tk.W, pady=(0, 10))

        # Context snippet display
        if self.context_snippet:
            f_ctx = ttk.LabelFrame(f, text="Context Snippet", padding=8)
            f_ctx.pack(fill=tk.X, pady=(0, 10))
            lbl_ctx = ttk.Label(
                f_ctx,
                text=f"... {self.context_snippet} ...",
                font=("Segoe UI", 9, "italic"),
                wraplength=460
            )
            lbl_ctx.pack(anchor=tk.W)

        # Input fields
        f_fields = ttk.Frame(f)
        f_fields.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(f_fields, text="Incorrect / Spoken Word:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky=tk.W, pady=4)
        self.entry_wrong = ttk.Entry(f_fields, font=("Segoe UI", 10), width=28)
        self.entry_wrong.grid(row=0, column=1, sticky=tk.EW, padx=(8, 0), pady=4)
        self.entry_wrong.insert(0, self.initial_word)

        ttk.Label(f_fields, text="Corrected Word / Phrase:", font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky=tk.W, pady=4)
        self.entry_right = ttk.Entry(f_fields, font=("Segoe UI", 10), width=28)
        self.entry_right.grid(row=1, column=1, sticky=tk.EW, padx=(8, 0), pady=4)
        self.entry_right.focus_set()

        f_fields.columnconfigure(1, weight=1)

        # Replacement Scope Options
        f_scope = ttk.LabelFrame(f, text="Correction Scope", padding=8)
        f_scope.pack(fill=tk.X, pady=(0, 10))

        self.scope_var = tk.StringVar(value="selected" if self.has_selection else "all")

        rb_sel = ttk.Radiobutton(
            f_scope,
            text="🎯 Fix ONLY this single selected word (leaves other identical words untouched)",
            variable=self.scope_var,
            value="selected"
        )
        rb_sel.pack(anchor=tk.W, pady=2)
        if not self.has_selection:
            rb_sel.config(state=tk.DISABLED)

        rb_all = ttk.Radiobutton(
            f_scope,
            text="🌐 Replace ALL occurrences of this word in current transcript",
            variable=self.scope_var,
            value="all"
        )
        rb_all.pack(anchor=tk.W, pady=2)

        # Permanent Library checkbox
        self.var_save_lib = tk.BooleanVar(value=False)
        cb_lib = ttk.Checkbutton(
            f,
            text="⭐ Save to Library (preferences.json)\n"
                 "    Automatically applies this correction to ALL future transcriptions.",
            variable=self.var_save_lib
        )
        cb_lib.pack(anchor=tk.W, pady=(0, 14))

        # Action Buttons
        f_btn = ttk.Frame(f)
        f_btn.pack(fill=tk.X, side=tk.BOTTOM)

        btn_apply = ttk.Button(f_btn, text="Apply Correction", style="Primary.TButton", command=self._apply)
        btn_apply.pack(side=tk.RIGHT, padx=(6, 0))

        btn_cancel = ttk.Button(f_btn, text="Cancel", command=self.destroy)
        btn_cancel.pack(side=tk.RIGHT)

        self.bind("<Return>", lambda e: self._apply())
        self.bind("<Escape>", lambda e: self.destroy())

    def _apply(self):
        wrong = self.entry_wrong.get().strip()
        right = self.entry_right.get().strip()

        if not wrong or not right:
            messagebox.showwarning("Input Required", "Both incorrect word and corrected word are required.", parent=self)
            return

        if self.on_fixed:
            self.on_fixed(
                wrong=wrong,
                right=right,
                save_to_lib=self.var_save_lib.get(),
                scope=self.scope_var.get(),
                is_urdu=self.is_urdu_tab,
                sel_range=self.selection_range
            )
        self.destroy()


# ════════════════════════════════════════════════════════════════════════════
# COLLAPSIBLE SECTION WIDGET
# ════════════════════════════════════════════════════════════════════════════

class CollapsibleSection(ttk.Frame):
    """A clean collapsible card container with a clickable header bar."""
    def __init__(self, parent, title: str, color_key: str = "neutral", default_open: bool = True):
        super().__init__(parent)
        self.pack(fill=tk.X, pady=(0, 8), padx=(0, 2))
        self.is_open = default_open
        self.title_text = title
        self.color_key = color_key

        # Header Frame
        self.header_frame = tk.Frame(self, relief="flat", bd=0)
        self.header_frame.pack(fill=tk.X)

        self.header_btn = tk.Button(
            self.header_frame,
            text=f"▾  {self.title_text}" if self.is_open else f"▸  {self.title_text}",
            anchor="w",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            bd=0,
            padx=10,
            pady=7,
            cursor="hand2",
            command=self.toggle
        )
        self.header_btn.pack(fill=tk.X)

        # Content frame
        self.content = ttk.Frame(self, padding=(10, 8, 10, 8), style="Card.TFrame")
        if self.is_open:
            self.content.pack(fill=tk.X, expand=True)

    def toggle(self):
        if self.is_open:
            self.content.pack_forget()
            self.is_open = False
            self.header_btn.config(text=f"▸  {self.title_text}")
        else:
            self.content.pack(fill=tk.X, expand=True)
            self.is_open = True
            self.header_btn.config(text=f"▾  {self.title_text}")

    def apply_theme(self, theme_arg):
        if isinstance(theme_arg, dict):
            tokens = theme_arg
        else:
            tokens = THEME_TOKENS["dark"] if theme_arg else THEME_TOKENS["light"]

        bg = tokens.get("btn_bg", tokens["elevated_surface"])
        fg = tokens["primary_text"]
        border = tokens["border"]
        self.header_frame.config(bg=bg, highlightbackground=border, highlightthickness=1)
        self.header_btn.config(bg=bg, fg=fg, activebackground=tokens.get("btn_hover", border), activeforeground=fg)


# ════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION WINDOW
# ════════════════════════════════════════════════════════════════════════════

class TranscribeApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Local Speech Studio (Whisper Large-v3-Turbo)")
        self.root.geometry("1400x880")
        self.root.minsize(1100, 680)

        # State variables
        self.current_theme = "dark"
        self.current_filepath: Optional[Path] = None
        self.is_transcribing = False
        self.cancel_flag = threading.Event()
        self.timer_start = 0.0
        self._spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._spinner_idx = 0
        self.is_inspector_visible = True
        self.waveform_peaks: List[tuple] = []
        self.is_waveform_dragging = False

        # Current transcript data
        self.current_segments: List[Any] = []
        self.current_info: Any = None
        self.raw_roman_text: str = ""
        self.raw_urdu_text: str = ""
        self.timed_words_urdu: List[dict] = []
        self.timed_words_roman: List[dict] = []

        # Synchronized Audio Player & Follow-Along Highlight State
        self.player = AudioPlayer()
        self.aligned_spans_roman: List[dict] = []
        self.aligned_spans_urdu: List[dict] = []
        self.current_highlight_word: Optional[dict] = None
        self.is_slider_dragging: bool = False
        self.var_autoscroll = tk.BooleanVar(value=True)
        self.seek_var = tk.DoubleVar(value=0.0)
        self.vol_var = tk.DoubleVar(value=1.0)

        # Retained compatibility entry for scripts / test suites
        self.entry_path = ttk.Entry(self.root)

        self._configure_styles()
        self._build_layout()
        self._load_saved_settings()

        # Start periodic audio player polling loop (25 fps)
        self.root.after(40, self._player_tick)

        # Check ffmpeg on startup
        if not shutil.which("ffmpeg"):
            self.root.after(500, self._warn_missing_ffmpeg)

    def _configure_styles(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # Typography defaults
        self.style.configure(".", font=("Segoe UI", 10))
        self.style.configure("TFrame", background="#111827")
        self.style.configure("Card.TFrame", background="#202D42", relief="flat")
        self.style.configure("TLabel", background="#111827", foreground="#F3F6FC")
        self.style.configure("Card.TLabel", background="#202D42", foreground="#F3F6FC")
        self.style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground="#F3F6FC")
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 9), foreground="#A7B4C7")
        self.style.configure("Status.TLabel", font=("Segoe UI", 9, "bold"), foreground="#4F8CFF")

        # Button Styles
        self.style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=6, background="#4F8CFF", foreground="#ffffff")
        self.style.map("Primary.TButton",
                       background=[("active", "#3D78E8"), ("disabled", "#344256"), ("!disabled", "#4F8CFF")],
                       foreground=[("!disabled", "#ffffff"), ("disabled", "#78869B")])

        self.style.configure("Secondary.TButton", font=("Segoe UI", 9), padding=5, background="#202D42", foreground="#F3F6FC")
        self.style.map("Secondary.TButton",
                       background=[("active", "#344256"), ("disabled", "#182235"), ("!disabled", "#202D42")],
                       foreground=[("!disabled", "#F3F6FC")])

        self.style.configure("Success.TButton", font=("Segoe UI", 9, "bold"), padding=5, background="#2FBF83", foreground="#ffffff")
        self.style.map("Success.TButton",
                       background=[("active", "#229c69"), ("disabled", "#344256"), ("!disabled", "#2FBF83")],
                       foreground=[("!disabled", "#ffffff")])

        self.style.configure("Warning.TButton", font=("Segoe UI", 9, "bold"), padding=5, background="#E7A743", foreground="#ffffff")
        self.style.map("Warning.TButton",
                       background=[("active", "#c9892c"), ("disabled", "#344256"), ("!disabled", "#E7A743")],
                       foreground=[("!disabled", "#ffffff")])

        self.style.configure("Danger.TButton", font=("Segoe UI", 9), padding=5, background="#E16B70", foreground="#ffffff")
        self.style.map("Danger.TButton",
                       background=[("active", "#be4f54"), ("disabled", "#344256"), ("!disabled", "#E16B70")],
                       foreground=[("!disabled", "#ffffff")])

        self.root.configure(background="#111827")

    def _build_layout(self):
        # Master root container
        self.main_container = tk.Frame(self.root, bg="#111827")
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Region 1: Application Header / Global Toolbar
        self._build_header_region()

        # Region 2: Project / Audio Information Strip
        self._build_info_strip_region()

        # Region 3: Workspace Container (Empty State vs Editor PanedWindow)
        self.workspace_container = tk.Frame(self.main_container, bg="#111827")
        self.workspace_container.pack(fill=tk.BOTH, expand=True, padx=14, pady=(6, 4))

        # 3A: Empty State Drop Zone
        self._build_empty_state()

        # 3B: Dual-Pane Editor Workspace (Transcript & Waveform vs Inspector)
        self._build_editor_workspace()

        # Region 4: Bottom Status Bar
        self._build_status_bar()

        # Global Keyboard Shortcuts
        self._bind_shortcuts()

        # Default to empty state if no file loaded
        self._show_empty_state()

    def _build_header_region(self):
        tokens = THEME_TOKENS.get(self.current_theme, THEME_TOKENS["dark"])
        self.header_frame = tk.Frame(
            self.main_container,
            height=52,
            padx=16,
            pady=8,
            bg=tokens["primary_surface"],
            highlightbackground=tokens["border"],
            highlightthickness=1,
            bd=0
        )
        self.header_frame.pack(fill=tk.X)

        # Left: App Logo & Title
        self.header_left = tk.Frame(self.header_frame, bg=tokens["primary_surface"])
        self.header_left.pack(side=tk.LEFT)

        self.lbl_app_logo = tk.Label(self.header_left, text="🎙️", font=("Segoe UI", 13), bg=tokens["primary_surface"])
        self.lbl_app_logo.pack(side=tk.LEFT, padx=(0, 6))

        self.lbl_app_title = tk.Label(
            self.header_left,
            text="Local Speech Studio",
            font=("Segoe UI", 12, "bold"),
            bg=tokens["primary_surface"],
            fg=tokens["primary_text"]
        )
        self.lbl_app_title.pack(side=tk.LEFT)

        self.lbl_local_pill = tk.Label(
            self.header_left,
            text=" ● LOCAL ASR ENGINE ",
            font=("Segoe UI", 8, "bold"),
            bg=tokens["elevated_surface"],
            fg=tokens["success"],
            padx=6,
            pady=2
        )
        self.lbl_local_pill.pack(side=tk.LEFT, padx=(10, 0))

        self.lbl_busy_badge = tk.Label(
            self.header_left,
            text=" [ ● READY ] ",
            font=("Consolas", 8, "bold"),
            bg=tokens["elevated_surface"],
            fg="#10b981",
            padx=4,
            pady=2
        )
        self.lbl_busy_badge.pack(side=tk.LEFT, padx=(6, 0))

        # Right: Action Buttons
        self.header_right = tk.Frame(self.header_frame, bg=tokens["primary_surface"])
        self.header_right.pack(side=tk.RIGHT)

        self.btn_header_undo = ttk.Button(self.header_right, text="↶ Undo", style="Secondary.TButton", width=7, command=self._undo_active)
        self.btn_header_undo.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_header_redo = ttk.Button(self.header_right, text="↷ Redo", style="Secondary.TButton", width=7, command=self._redo_active)
        self.btn_header_redo.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_theme = ttk.Button(self.header_right, text="☀️ Light Mode", style="Secondary.TButton", command=self._toggle_theme)
        self.btn_theme.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_preferences = ttk.Button(self.header_right, text="⚙ Preferences", style="Secondary.TButton", command=self._open_preferences)
        self.btn_preferences.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_hardware = ttk.Button(self.header_right, text="⚡ Hardware", style="Secondary.TButton", command=self._show_hardware_info)
        self.btn_hardware.pack(side=tk.LEFT)

    def _build_info_strip_region(self):
        tokens = THEME_TOKENS.get(self.current_theme, THEME_TOKENS["dark"])
        self.info_strip_frame = tk.Frame(
            self.main_container,
            padx=16,
            pady=8,
            bg=tokens["elevated_surface"],
            highlightbackground=tokens["border"],
            highlightthickness=1,
            bd=0
        )

        self.info_left = tk.Frame(self.info_strip_frame, bg=tokens["elevated_surface"])
        self.info_left.pack(side=tk.LEFT, fill=tk.Y)

        self.lbl_info_filename = tk.Label(self.info_left, text="", font=("Segoe UI", 10, "bold"), bg=tokens["elevated_surface"], fg=tokens["primary_text"])
        self.lbl_info_filename.pack(anchor=tk.W)

        self.info_sub = tk.Frame(self.info_left, bg=tokens["elevated_surface"])
        self.info_sub.pack(anchor=tk.W, pady=(2, 0))

        self.lbl_info_meta = tk.Label(self.info_sub, text="", font=("Segoe UI", 9), bg=tokens["elevated_surface"], fg=tokens["secondary_text"])
        self.lbl_info_meta.pack(side=tk.LEFT)

        self.lbl_info_status = tk.Label(self.info_sub, text="", font=("Segoe UI", 9, "bold"), bg=tokens["elevated_surface"], fg=tokens["accent"])
        self.lbl_info_status.pack(side=tk.LEFT, padx=(10, 0))

        # ETA timer
        self.lbl_timer = ttk.Label(self.info_strip_frame, text="", style="SubHeader.TLabel")
        self.lbl_timer.pack(side=tk.LEFT, padx=(16, 0))

        self.prog_bar = ttk.Progressbar(self.info_strip_frame, mode="indeterminate", length=140)

        # Right actions
        self.info_actions = tk.Frame(self.info_strip_frame, bg=tokens["elevated_surface"])
        self.info_actions.pack(side=tk.RIGHT)

        self.btn_replace = ttk.Button(self.info_actions, text="📁 Replace File...", style="Secondary.TButton", command=self._browse_file)
        self.btn_replace.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_start = ttk.Button(self.info_actions, text="▶ Transcribe Audio", style="Primary.TButton", command=self._start_transcription)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_cancel = ttk.Button(self.info_actions, text="Cancel", style="Danger.TButton", state=tk.DISABLED, command=self._cancel_transcription)
        self.btn_cancel.pack(side=tk.LEFT)

    def _build_empty_state(self):
        tokens = THEME_TOKENS.get(self.current_theme, THEME_TOKENS["dark"])
        self.empty_state_frame = tk.Frame(self.workspace_container, bg=tokens["app_bg"], relief="flat", bd=0)
        self.empty_state_frame.pack(fill=tk.BOTH, expand=True)

        self.empty_state_card = tk.Frame(
            self.empty_state_frame,
            bg=tokens["elevated_surface"],
            highlightbackground=tokens["border"],
            highlightcolor=tokens["border"],
            highlightthickness=1,
            bd=0,
            padx=48,
            pady=36
        )
        self.empty_state_card.place(relx=0.5, rely=0.48, anchor="center")

        self.lbl_empty_icon = tk.Label(self.empty_state_card, text="🎙️", font=("Segoe UI", 36), bg=tokens["elevated_surface"])
        self.lbl_empty_icon.pack(pady=(0, 10))

        self.lbl_empty_title = tk.Label(
            self.empty_state_card,
            text="Open an Audio or Video File",
            font=("Segoe UI", 16, "bold"),
            bg=tokens["elevated_surface"],
            fg=tokens["primary_text"]
        )
        self.lbl_empty_title.pack(pady=(0, 6))

        self.lbl_empty_sub = tk.Label(
            self.empty_state_card,
            text="Choose a media file to transcribe locally with Whisper Large-v3-Turbo.",
            font=("Segoe UI", 10),
            bg=tokens["elevated_surface"],
            fg=tokens["secondary_text"]
        )
        self.lbl_empty_sub.pack(pady=(0, 18))

        btn_browse = ttk.Button(
            self.empty_state_card,
            text="📁 Browse Media Files...",
            style="Primary.TButton",
            padding=10,
            command=self._browse_file
        )
        btn_browse.pack(pady=(0, 16))

        self.lbl_empty_formats = tk.Label(
            self.empty_state_card,
            text="Supported formats: WAV • MP3 • MP4 • MKV • M4A • FLAC • AAC • OGG • WebM",
            font=("Segoe UI", 9),
            bg=tokens["elevated_surface"],
            fg=tokens["muted_text"]
        )
        self.lbl_empty_formats.pack(pady=(0, 8))

        self.lbl_empty_privacy = tk.Label(
            self.empty_state_card,
            text="🔒 100% Local & Offline — Audio is processed entirely on your hardware and never uploaded to the cloud.",
            font=("Segoe UI", 8),
            bg=tokens["elevated_surface"],
            fg=tokens["muted_text"]
        )
        self.lbl_empty_privacy.pack()

    def _build_editor_workspace(self):
        self.editor_split = ttk.PanedWindow(self.workspace_container, orient=tk.HORIZONTAL)

        # ── Left Container: Transcript & Waveform Timeline Player (70%) ───────
        self.left_container = ttk.Frame(self.editor_split, padding=(0, 0, 8, 0))
        self.editor_split.add(self.left_container, weight=3)

        # Top Text Panel Toolbar
        self.text_toolbar = ttk.Frame(self.left_container, padding=(2, 0, 2, 6))
        self.text_toolbar.pack(fill=tk.X)

        self.lbl_counts = ttk.Label(self.text_toolbar, text="Words: 0  •  Characters: 0", style="SubHeader.TLabel")
        self.lbl_counts.pack(side=tk.LEFT, pady=4)

        self.btn_play_sel = ttk.Button(self.text_toolbar, text="▶ Play Selection", style="Secondary.TButton", command=self._play_selected_span)
        self.btn_play_sel.pack(side=tk.LEFT, padx=(16, 0))

        self.btn_clear = ttk.Button(self.text_toolbar, text="🧹 Clear", style="Danger.TButton", command=self._clear_active_text)
        self.btn_clear.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_copy = ttk.Button(self.text_toolbar, text="📋 Copy", command=self._copy_active_text)
        self.btn_copy.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_fix_word = ttk.Button(self.text_toolbar, text="🎯 Fix Word", style="Warning.TButton", command=self._fix_selected_word)
        self.btn_fix_word.pack(side=tk.RIGHT)

        # Tabs for Transcripts
        self.notebook = ttk.Notebook(self.left_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Tab 1: Roman Urdu
        tab_roman = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab_roman, text="  🔤 Roman Urdu Transcript  ")

        self.txt_roman = tk.Text(tab_roman, wrap=tk.WORD, font=("Segoe UI", 11), undo=True, maxundo=-1, padx=14, pady=14, spacing1=3, spacing3=3)
        scroll_roman = ttk.Scrollbar(tab_roman, orient=tk.VERTICAL, command=self.txt_roman.yview)
        self.txt_roman.configure(yscrollcommand=scroll_roman.set)
        self.txt_roman.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_roman.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_roman.bind("<KeyRelease>", lambda e: self._update_counts())
        self.txt_roman.bind("<Button-1>", self._on_transcript_click)
        self.txt_roman.bind("<Double-Button-1>", self._on_transcript_double_click)
        self.txt_roman.bind("<<Selection>>", self._on_selection_change)

        # Tab 2: Urdu Script (RTL)
        tab_urdu = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab_urdu, text="  ✍️ Urdu Script Transcript  ")

        self.txt_urdu = tk.Text(tab_urdu, wrap=tk.WORD, font=("Segoe UI", 13), undo=True, maxundo=-1, padx=14, pady=14, spacing1=3, spacing3=3)
        scroll_urdu = ttk.Scrollbar(tab_urdu, orient=tk.VERTICAL, command=self.txt_urdu.yview)
        self.txt_urdu.configure(yscrollcommand=scroll_urdu.set)
        self.txt_urdu.tag_configure("rtl", justify="right")
        self.txt_urdu.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_urdu.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_urdu.bind("<KeyRelease>", lambda e: self._update_counts())
        self.txt_urdu.bind("<Button-1>", self._on_transcript_click)
        self.txt_urdu.bind("<Double-Button-1>", self._on_transcript_double_click)
        self.txt_urdu.bind("<<Selection>>", self._on_selection_change)

        self._build_context_menu()

        # ── Bottom Player & Waveform Timeline Card ───────────────────────────
        self.player_card = ttk.Frame(self.left_container, style="Card.TFrame", padding=(10, 8, 10, 8))
        self.player_card.pack(fill=tk.X, pady=(6, 0))

        # Waveform Canvas
        self.canvas_waveform = tk.Canvas(self.player_card, height=48, highlightthickness=0, cursor="hand2")
        self.canvas_waveform.pack(fill=tk.X, pady=(0, 6))
        self.canvas_waveform.bind("<Configure>", lambda e: self._draw_waveform())
        self.canvas_waveform.bind("<Button-1>", self._on_waveform_interact)
        self.canvas_waveform.bind("<B1-Motion>", self._on_waveform_interact)

        # Transport Controls Row
        f_play_ctrls = ttk.Frame(self.player_card, style="Card.TFrame")
        f_play_ctrls.pack(fill=tk.X)

        self.btn_play_pause = ttk.Button(f_play_ctrls, text="▶ Play", style="Primary.TButton", width=7, command=self._toggle_play_pause)
        self.btn_play_pause.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_stop = ttk.Button(f_play_ctrls, text="⏹ Stop", width=6, command=self._stop_playback)
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_rw = ttk.Button(f_play_ctrls, text="⏪ -5s", width=6, command=lambda: self._jump_relative(-5.0))
        self.btn_rw.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_ff = ttk.Button(f_play_ctrls, text="⏩ +5s", width=6, command=lambda: self._jump_relative(5.0))
        self.btn_ff.pack(side=tk.LEFT, padx=(0, 8))

        # Timeline Seek Scale
        self.slider_seek = ttk.Scale(f_play_ctrls, from_=0.0, to=100.0, orient=tk.HORIZONTAL, variable=self.seek_var)
        self.slider_seek.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.slider_seek.bind("<ButtonPress-1>", self._on_slider_press)
        self.slider_seek.bind("<ButtonRelease-1>", self._on_slider_release)

        # Time display
        self.lbl_player_time = ttk.Label(f_play_ctrls, text="00:00.0 / 00:00.0", font=("Segoe UI", 9, "bold"), style="SubHeader.TLabel")
        self.lbl_player_time.pack(side=tk.LEFT, padx=(0, 8))

        # Volume control
        self.lbl_vol_icon = ttk.Label(f_play_ctrls, text="🔊", style="SubHeader.TLabel")
        self.lbl_vol_icon.pack(side=tk.LEFT, padx=(0, 2))
        self.slider_vol = ttk.Scale(f_play_ctrls, from_=0.0, to=1.5, value=1.0, orient=tk.HORIZONTAL, length=65, variable=self.vol_var, command=self._on_volume_change)
        self.slider_vol.pack(side=tk.LEFT, padx=(0, 8))

        # Follow Text Checkbox
        self.chk_autoscroll = ttk.Checkbutton(f_play_ctrls, text="Follow Text", variable=self.var_autoscroll)
        self.chk_autoscroll.pack(side=tk.LEFT)

        # ── Right Container: Contextual Inspector Panel (30%) ────────────────
        self.inspector_container = ttk.Frame(self.editor_split, padding=(6, 0, 0, 0))
        self.editor_split.add(self.inspector_container, weight=1)

        f_insp_hdr = ttk.Frame(self.inspector_container)
        f_insp_hdr.pack(fill=tk.X, pady=(0, 6))

        lbl_insp_title = ttk.Label(f_insp_hdr, text="INSPECTOR", font=("Segoe UI", 9, "bold"), style="SubHeader.TLabel")
        lbl_insp_title.pack(side=tk.LEFT, pady=2)

        self.btn_toggle_inspector = ttk.Button(f_insp_hdr, text="▶ Hide Inspector", style="Secondary.TButton", command=self._toggle_inspector)
        self.btn_toggle_inspector.pack(side=tk.RIGHT)

        # Scrollable Canvas container for Inspector
        self.canvas_inspector = tk.Canvas(self.inspector_container, highlightthickness=0)
        scroll_insp = ttk.Scrollbar(self.inspector_container, orient=tk.VERTICAL, command=self.canvas_inspector.yview)
        self.scrollable_inspector = ttk.Frame(self.canvas_inspector)

        self.scrollable_inspector.bind(
            "<Configure>",
            lambda e: self.canvas_inspector.configure(scrollregion=self.canvas_inspector.bbox("all"))
        )
        insp_window = self.canvas_inspector.create_window((0, 0), window=self.scrollable_inspector, anchor="nw")
        self.canvas_inspector.bind("<Configure>", lambda e: self.canvas_inspector.itemconfig(insp_window, width=e.width))
        self.canvas_inspector.configure(yscrollcommand=scroll_insp.set)

        self.canvas_inspector.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_insp.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            if self.canvas_inspector.winfo_height() < self.scrollable_inspector.winfo_height():
                self.canvas_inspector.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.canvas_inspector.bind_all(
            "<MouseWheel>",
            lambda event: _on_mousewheel(event) if (str(event.widget).startswith(str(self.canvas_inspector)) or str(event.widget).startswith(str(self.scrollable_inspector))) else None
        )

        self._build_inspector_sections()

    def _build_context_menu(self):
        self.menu_context = tk.Menu(self.root, tearoff=0)
        self.menu_context.add_command(label="🎯 Fix Selected Word / Add to Library...", command=self._fix_selected_word)
        self.menu_context.add_command(label="▶ Play Audio for Selection", command=self._play_selected_span)
        self.menu_context.add_separator()
        self.menu_context.add_command(label="Cut", command=lambda: self.root.focus_get().event_generate("<<Cut>>"))
        self.menu_context.add_command(label="Copy", command=lambda: self.root.focus_get().event_generate("<<Copy>>"))
        self.menu_context.add_command(label="Paste", command=lambda: self.root.focus_get().event_generate("<<Paste>>"))
        self.menu_context.add_separator()
        self.menu_context.add_command(label="Select All", command=lambda: self.root.focus_get().tag_add("sel", "1.0", "end"))

        def _show_context_menu(event):
            widget = event.widget
            try:
                if not widget.tag_ranges("sel"):
                    click_idx = widget.index(f"@{event.x},{event.y}")
                    word_start = widget.index(f"{click_idx} wordstart")
                    word_end = widget.index(f"{click_idx} wordend")
                    word_str = widget.get(word_start, word_end).strip()
                    if word_str:
                        widget.tag_remove("sel", "1.0", "end")
                        widget.tag_add("sel", word_start, word_end)
                        widget.mark_set("insert", word_end)
            except Exception:
                pass
            self.menu_context.tk_popup(event.x_root, event.y_root)

        self.txt_roman.bind("<Button-3>", _show_context_menu)
        self.txt_urdu.bind("<Button-3>", _show_context_menu)

    def _build_inspector_sections(self):
        # Section A: Selection & Text Tools
        self.sec_selection = CollapsibleSection(self.scrollable_inspector, "Selection & Text Tools", default_open=True)

        self.lbl_sel_info = ttk.Label(self.sec_selection.content, text="No text selected.\nClick or highlight words to inspect.", style="SubHeader.TLabel", wraplength=260)
        self.lbl_sel_info.pack(anchor=tk.W, pady=(0, 6))

        self.btn_fix_word_insp = ttk.Button(self.sec_selection.content, text="🎯 Fix Selected Word...", style="Warning.TButton", command=self._fix_selected_word)
        self.btn_fix_word_insp.pack(fill=tk.X, pady=(0, 6))

        # Find & Replace
        f_fr1 = ttk.Frame(self.sec_selection.content)
        f_fr1.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(f_fr1, text="Find:").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_find = ttk.Entry(f_fr1, font=("Segoe UI", 9))
        self.entry_find.pack(side=tk.LEFT, fill=tk.X, expand=True)

        f_fr2 = ttk.Frame(self.sec_selection.content)
        f_fr2.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(f_fr2, text="Replace:").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_replace = ttk.Entry(f_fr2, font=("Segoe UI", 9))
        self.entry_replace.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(f_fr2, text="Replace All", command=self._find_and_replace).pack(side=tk.LEFT)

        # Quick cleanup actions
        f_clean = ttk.Frame(self.sec_selection.content)
        f_clean.pack(fill=tk.X, pady=(0, 2))
        ttk.Button(f_clean, text="Aa Capitalize", command=self._apply_casing).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        ttk.Button(f_clean, text="✂ Strip Punctuation", command=self._strip_punctuation).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))

        # Section B: Transcription & Model Settings
        self.sec_model = CollapsibleSection(self.scrollable_inspector, "Transcription & Model Settings", default_open=True)

        f_m = ttk.Frame(self.sec_model.content)
        f_m.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(f_m, text="ASR Model:").pack(anchor=tk.W, pady=(0, 2))
        self.combo_model = ttk.Combobox(
            f_m,
            values=[
                "Whisper Large-v3-Turbo (Faster-Whisper • 809M)",
                "Whisper Large-v3 (High Accuracy • 1550M • GPU/CPU)",
                "Loudness-ai/urdu-sukhan-asr-v1 (Urdu Sukhan ASR v1)"
            ],
            state="readonly"
        )
        self.combo_model.current(0)
        self.combo_model.pack(fill=tk.X)

        f_d = ttk.Frame(self.sec_model.content)
        f_d.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(f_d, text="Compute Device:").pack(anchor=tk.W, pady=(0, 2))
        self.combo_device = ttk.Combobox(
            f_d,
            values=[
                "Auto (GPU if available, else CPU)",
                "GPU (Force CUDA Acceleration)",
                "CPU (8 Threads • int8)"
            ],
            state="readonly"
        )
        self.combo_device.current(0)
        self.combo_device.pack(fill=tk.X)

        f_dev_status = ttk.Frame(self.sec_model.content)
        f_dev_status.pack(fill=tk.X, pady=(0, 6))
        self.lbl_device_info = ttk.Label(f_dev_status, text="", style="SubHeader.TLabel", wraplength=260)
        self.lbl_device_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(f_dev_status, text="⚡ Info", width=6, command=self._show_hardware_info).pack(side=tk.RIGHT)

        f_l = ttk.Frame(self.sec_model.content)
        f_l.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(f_l, text="Language Mode:").pack(anchor=tk.W, pady=(0, 2))
        self.combo_lang = ttk.Combobox(
            f_l,
            values=[
                "Auto-detect (Default)",
                "Urdu + English Mixed",
                "Pure English"
            ],
            state="readonly"
        )
        self.combo_lang.current(0)
        self.combo_lang.pack(fill=tk.X)

        # Section C: Output Formatting
        self.sec_tweaks = CollapsibleSection(self.scrollable_inspector, "Output Formatting", default_open=True)

        ttk.Label(self.sec_tweaks.content, text="Subtitle Timing Style:").pack(anchor=tk.W, pady=(0, 2))
        self.combo_srt_style = ttk.Combobox(
            self.sec_tweaks.content,
            values=[
                "Word-by-word (Karaoke / 1 word per subtitle)",
                "Grouped (2 - 4 words per subtitle)",
                "Phrase-level (5 - 8 words per subtitle)",
                "Sentence / Line-level (Full sentence cues)"
            ],
            state="readonly"
        )
        self.combo_srt_style.current(0)
        self.combo_srt_style.pack(fill=tk.X, pady=(0, 6))

        ttk.Button(self.sec_tweaks.content, text="🔄 Re-transliterate Roman Urdu", command=self._retransliterate_roman).pack(fill=tk.X, pady=(0, 2))

        # Section D: Export Options
        self.sec_exports = CollapsibleSection(self.scrollable_inspector, "Export & Outputs", default_open=True)

        ttk.Button(self.sec_exports.content, text="📦 Export All (4 Files)", style="Success.TButton", command=self._export_all).pack(fill=tk.X, pady=(0, 6))
        ttk.Button(self.sec_exports.content, text="💾 Export Plain Text (.txt)", command=self._export_plain_text).pack(fill=tk.X, pady=(0, 4))
        ttk.Button(self.sec_exports.content, text="🎬 Export Subtitles (.srt)", command=self._export_subtitles).pack(fill=tk.X, pady=(0, 4))
        ttk.Button(self.sec_exports.content, text="📂 Open Output Folder", command=self._open_output_folder).pack(fill=tk.X)

    def _build_status_bar(self):
        tokens = THEME_TOKENS.get(self.current_theme, THEME_TOKENS["dark"])
        self.status_bar_frame = tk.Frame(
            self.main_container,
            height=28,
            padx=16,
            pady=4,
            bg=tokens["primary_surface"],
            highlightbackground=tokens["border"],
            highlightthickness=1,
            bd=0
        )
        self.status_bar_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.lbl_status_engine = tk.Label(
            self.status_bar_frame,
            text="Local processing  •  Whisper Large-v3-Turbo  •  100% Offline",
            font=("Segoe UI", 9),
            bg=tokens["primary_surface"],
            fg=tokens["secondary_text"]
        )
        self.lbl_status_engine.pack(side=tk.LEFT)

        self.lbl_status_metrics = tk.Label(
            self.status_bar_frame,
            text="0 words  •  0 characters  •  0 selected",
            font=("Segoe UI", 9),
            bg=tokens["primary_surface"],
            fg=tokens["secondary_text"]
        )
        self.lbl_status_metrics.pack(side=tk.RIGHT)

        # Compatibility alias for lbl_status
        self.lbl_status = self.lbl_status_engine

    def _bind_shortcuts(self):
        self.root.bind("<Control-o>", lambda e: self._browse_file())
        self.root.bind("<Control-s>", lambda e: self._export_plain_text())
        self.root.bind("<Control-S>", lambda e: self._export_subtitles())
        self.root.bind("<F5>", lambda e: self._start_transcription())
        self.root.bind("<Control-space>", lambda e: self._toggle_play_pause())
        self.root.bind("<Control-Left>", lambda e: self._jump_relative(-5.0))
        self.root.bind("<Control-Right>", lambda e: self._jump_relative(5.0))
        self.root.bind("<Control-z>", lambda e: self._undo_active())
        self.root.bind("<Control-y>", lambda e: self._redo_active())
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)

    # ── State Transitions: Empty State vs Editor Workspace ───────────────────

    def _show_empty_state(self):
        """Displays the centered drop zone when no audio file is loaded."""
        if hasattr(self, "info_strip_frame"):
            self.info_strip_frame.pack_forget()
        if hasattr(self, "editor_split"):
            self.editor_split.pack_forget()
        if hasattr(self, "empty_state_frame"):
            self.empty_state_frame.pack(fill=tk.BOTH, expand=True)
        self.lbl_status_engine.config(text="Local processing  •  Ready  •  No media file loaded")

    def _show_editor_state(self, filepath: Path):
        """Switches from empty state to the full dual-pane editor workspace."""
        if hasattr(self, "empty_state_frame"):
            self.empty_state_frame.pack_forget()
        if hasattr(self, "info_strip_frame"):
            self.info_strip_frame.pack(fill=tk.X, after=self.header_frame)
        if hasattr(self, "editor_split"):
            self.editor_split.pack(fill=tk.BOTH, expand=True)

        self.current_filepath = filepath
        self.entry_path.delete(0, tk.END)
        self.entry_path.insert(0, str(filepath))

        info = get_file_info(filepath)
        self.lbl_info_filename.config(text=f"📁 {filepath.name}")
        self.lbl_info_meta.config(text=info)
        self.lbl_info_status.config(text="Ready to Transcribe")
        self._update_engine_status_bar()

    # ── Waveform & Timeline Visualization ────────────────────────────────────

    def _compute_waveform_peaks(self, audio_data: np.ndarray, num_bins: int = 800) -> list:
        """Vectorized downsampling of audio data into min/max amplitude peaks."""
        if audio_data is None or len(audio_data) == 0:
            return []
        total = len(audio_data)
        bin_size = max(1, total // num_bins)
        usable = (total // bin_size) * bin_size
        reshaped = audio_data[:usable].reshape(-1, bin_size)
        mins = np.min(reshaped, axis=1)
        maxs = np.max(reshaped, axis=1)
        return list(zip(mins.tolist(), maxs.tolist()))

    def _draw_waveform(self):
        """Draws waveform amplitude peaks onto canvas_waveform."""
        if not hasattr(self, "canvas_waveform"):
            return
        self.canvas_waveform.delete("all")
        width = self.canvas_waveform.winfo_width()
        height = self.canvas_waveform.winfo_height()
        if width <= 1:
            width = 800
        if height <= 1:
            height = 48

        tokens = THEME_TOKENS.get(self.current_theme, THEME_TOKENS["dark"])
        wave_color = tokens["waveform_wave"]
        bg_color = tokens["waveform_bg"]

        self.canvas_waveform.config(bg=bg_color)
        mid_y = height / 2.0

        if not self.waveform_peaks:
            self.canvas_waveform.create_line(0, mid_y, width, mid_y, fill=tokens["border"], tags="baseline")
            return

        peak_max = max(max(abs(mn), abs(mx)) for mn, mx in self.waveform_peaks) or 1.0
        scale = (mid_y * 0.88) / peak_max

        num_peaks = len(self.waveform_peaks)
        step = width / max(1, num_peaks)

        for i, (mn, mx) in enumerate(self.waveform_peaks):
            x = i * step
            y1 = mid_y - (mx * scale)
            y2 = mid_y - (mn * scale)
            if abs(y2 - y1) < 1.0:
                y2 = y1 + 1.0
            self.canvas_waveform.create_line(x, y1, x, y2, fill=wave_color, tags="wave")

        playhead_color = tokens["waveform_playhead"]
        cur_pos = self.player.get_position() if self.player.is_loaded() else 0.0
        dur = self.player.get_duration() or 1.0
        playhead_x = (cur_pos / dur) * width
        self.canvas_waveform.create_line(playhead_x, 0, playhead_x, height, fill=playhead_color, width=2, tags="playhead")

    def _update_playhead(self, cur_pos: float, total_dur: float):
        """Moves playhead line on waveform canvas to current playback position."""
        if not hasattr(self, "canvas_waveform") or total_dur <= 0:
            return
        width = self.canvas_waveform.winfo_width()
        height = self.canvas_waveform.winfo_height()
        if width <= 1:
            width = 800
        if height <= 1:
            height = 48

        x = (cur_pos / total_dur) * width
        self.canvas_waveform.coords("playhead", x, 0, x, height)
        self.canvas_waveform.tag_raise("playhead")

    def _on_waveform_interact(self, event):
        """Click or drag on waveform seeks playback to exact timestamp."""
        if not self.player.is_loaded():
            return
        dur = self.player.get_duration()
        if dur <= 0:
            return
        width = self.canvas_waveform.winfo_width() or 800
        target_t = max(0.0, min(dur, (event.x / width) * dur))
        self.player.seek(target_t)
        self.seek_var.set(target_t)
        self._update_playhead(target_t, dur)
        self.lbl_player_time.config(text=f"{format_playback_time(target_t)} / {format_playback_time(dur)}")

    # ── Text-Based Audio Editing Helpers ─────────────────────────────────────

    def _play_selected_span(self):
        """Plays only the audio corresponding to the currently selected text."""
        active_tab = self.notebook.index(self.notebook.select())
        txt_widget = self.txt_roman if active_tab == 0 else self.txt_urdu
        try:
            ranges = txt_widget.tag_ranges("sel")
            if not ranges:
                self._toggle_play_pause()
                return

            s_idx, e_idx = ranges[0], ranges[1]
            aligned = self.aligned_spans_roman if active_tab == 0 else self.aligned_spans_urdu
            sel_words = [it for it in aligned if txt_widget.compare(it["tk_start"], ">=", s_idx) and txt_widget.compare(it["tk_end"], "<=", e_idx)]
            if sel_words:
                start_t = sel_words[0]["start"]
                end_t = sel_words[-1]["end"]
                self.player.seek(start_t)
                self.player.play()
                self.btn_play_pause.config(text="⏸ Pause")
                play_dur = max(0.1, end_t - start_t)
                self.root.after(int(play_dur * 1000), lambda: self.player.pause() if self.player.is_playing else None)
        except Exception as exc:
            print(f"[PlaySelection] {exc}")

    def _undo_active(self):
        """Triggers undo on active transcript text widget."""
        active_tab = self.notebook.index(self.notebook.select())
        txt_widget = self.txt_roman if active_tab == 0 else self.txt_urdu
        try:
            txt_widget.edit_undo()
            self._update_counts()
            self._rebuild_word_spans()
        except tk.TclError:
            pass

    def _redo_active(self):
        """Triggers redo on active transcript text widget."""
        active_tab = self.notebook.index(self.notebook.select())
        txt_widget = self.txt_roman if active_tab == 0 else self.txt_urdu
        try:
            txt_widget.edit_redo()
            self._update_counts()
            self._rebuild_word_spans()
        except tk.TclError:
            pass

    def _on_selection_change(self, event=None):
        """Updates status bar and Inspector with selected text and timestamps."""
        try:
            active_tab = self.notebook.index(self.notebook.select())
            txt_widget = self.txt_roman if active_tab == 0 else self.txt_urdu
            ranges = txt_widget.tag_ranges("sel")
            if ranges and len(ranges) >= 2:
                s_idx, e_idx = ranges[0], ranges[1]
                sel_text = txt_widget.get(s_idx, e_idx).strip()
                words = len(sel_text.split())
                chars = len(sel_text)
                self.lbl_status_metrics.config(text=f"{words} words selected  •  {chars} characters")

                aligned = self.aligned_spans_roman if active_tab == 0 else self.aligned_spans_urdu
                sel_items = [it for it in aligned if txt_widget.compare(it["tk_start"], ">=", s_idx) and txt_widget.compare(it["tk_end"], "<=", e_idx)]
                if sel_items:
                    t_range = f"[{transcribe_pipeline.srt_time(sel_items[0]['start'])} --> {transcribe_pipeline.srt_time(sel_items[-1]['end'])}]"
                    snippet = sel_text if len(sel_text) <= 30 else sel_text[:27] + "..."
                    self.lbl_sel_info.config(text=f"Selected: \"{snippet}\"\n{t_range} ({len(sel_items)} words)")
                else:
                    snippet = sel_text if len(sel_text) <= 30 else sel_text[:27] + "..."
                    self.lbl_sel_info.config(text=f"Selected: \"{snippet}\" ({words} words)")
            else:
                self._update_counts()
                self.lbl_sel_info.config(text="No text selected.\nClick or highlight words to inspect.")
        except Exception:
            pass

    def _on_volume_change(self, val):
        vol = float(val)
        self.player.set_volume(vol)
        pct = int(vol * 100)
        self.lbl_vol_icon.config(text="🔇" if pct == 0 else ("🔉" if pct < 50 else "🔊"))

    def _toggle_inspector(self):
        """Collapses or expands the right-side inspector panel."""
        if self.is_inspector_visible:
            self.editor_split.forget(self.inspector_container)
            self.is_inspector_visible = False
            self.btn_toggle_inspector.config(text="◀ Show Inspector")
        else:
            self.editor_split.add(self.inspector_container, weight=1)
            self.is_inspector_visible = True
            self.btn_toggle_inspector.config(text="▶ Hide Inspector")

    def _update_engine_status_bar(self):
        """Updates the left engine description in the bottom status bar."""
        model_str = self.combo_model.get().split("(")[0].strip() if hasattr(self, "combo_model") else "Whisper Large-v3-Turbo"
        cuda_status = transcribe_pipeline.get_cuda_status()
        device_choice = self.combo_device.get() if hasattr(self, "combo_device") else "Auto"
        if cuda_status.get("cuda_available") and not device_choice.startswith("CPU"):
            dev_name = cuda_status.get("device_name", "GPU")
            dev_str = f"CUDA GPU ({dev_name})"
        else:
            dev_str = "CPU (int8)"
        self.lbl_status_engine.config(text=f"Local processing  •  {model_str}  •  {dev_str}  •  100% Offline")

    # ── User Actions & Event Handlers ────────────────────────────────────────

    def _browse_file(self):
        filetypes = [
            ("Supported Media", "*.wav *.mp3 *.m4a *.flac *.ogg *.aac *.opus *.mp4 *.mkv *.avi *.mov *.wmv *.webm *.m4v *.ts"),
            ("Audio Files", "*.wav *.mp3 *.m4a *.flac *.ogg *.aac *.opus *.wma"),
            ("Video Files", "*.mp4 *.mkv *.avi *.mov *.wmv *.webm *.m4v *.ts"),
            ("All Files", "*.*")
        ]
        chosen = filedialog.askopenfilename(title="Select Media to Transcribe", filetypes=filetypes)
        if chosen:
            p = Path(chosen)
            self._show_editor_state(p)
            self._load_audio_for_playback(p)

    def _open_preferences(self):
        PreferencesDialog(self.root, on_saved_callback=self._on_preferences_saved)

    def _show_hardware_info(self):
        HardwareInfoDialog(self.root)

    def _toggle_theme(self):
        new_theme = "dark" if self.current_theme == "light" else "light"
        self._apply_theme(new_theme)
        config_manager.set_setting("theme", new_theme)

    def _apply_theme(self, theme_name: str):
        self.current_theme = theme_name if theme_name in THEME_TOKENS else "dark"
        tokens = THEME_TOKENS[self.current_theme]
        is_dark = (self.current_theme == "dark")

        # 1. Root & Base containers
        self.root.configure(background=tokens["app_bg"])
        if hasattr(self, "main_container"):
            self.main_container.configure(bg=tokens["app_bg"])
        if hasattr(self, "workspace_container"):
            self.workspace_container.configure(bg=tokens["app_bg"])

        # Header Region
        if hasattr(self, "header_frame"):
            self.header_frame.configure(bg=tokens["primary_surface"], highlightbackground=tokens["border"])
        if hasattr(self, "header_left"):
            self.header_left.configure(bg=tokens["primary_surface"])
        if hasattr(self, "header_right"):
            self.header_right.configure(bg=tokens["primary_surface"])
        if hasattr(self, "lbl_app_title"):
            self.lbl_app_title.config(fg=tokens["primary_text"], bg=tokens["primary_surface"])
        if hasattr(self, "lbl_app_logo"):
            self.lbl_app_logo.config(bg=tokens["primary_surface"])
        if hasattr(self, "lbl_local_pill"):
            if is_dark:
                self.lbl_local_pill.config(fg=tokens["success"], bg=tokens["elevated_surface"], highlightbackground=tokens["border"], highlightthickness=1)
            else:
                self.lbl_local_pill.config(fg="#0f5132", bg="#d1e7dd", highlightbackground="#badbcc", highlightthickness=1)
        if hasattr(self, "lbl_busy_badge"):
            if is_dark:
                self.lbl_busy_badge.config(bg=tokens["elevated_surface"], fg="#10b981", highlightbackground=tokens["border"], highlightthickness=1)
            else:
                self.lbl_busy_badge.config(bg="#d1e7dd", fg="#0f5132", highlightbackground="#badbcc", highlightthickness=1)

        # Info Strip Region
        if hasattr(self, "info_strip_frame"):
            self.info_strip_frame.configure(bg=tokens["elevated_surface"], highlightbackground=tokens["border"])
        if hasattr(self, "info_left"):
            self.info_left.configure(bg=tokens["elevated_surface"])
        if hasattr(self, "info_sub"):
            self.info_sub.configure(bg=tokens["elevated_surface"])
        if hasattr(self, "info_actions"):
            self.info_actions.configure(bg=tokens["elevated_surface"])
        if hasattr(self, "lbl_info_filename"):
            self.lbl_info_filename.config(fg=tokens["primary_text"], bg=tokens["elevated_surface"])
        if hasattr(self, "lbl_info_meta"):
            self.lbl_info_meta.config(fg=tokens["secondary_text"], bg=tokens["elevated_surface"])
        if hasattr(self, "lbl_info_status"):
            self.lbl_info_status.config(fg=tokens["accent"], bg=tokens["elevated_surface"])

        # Empty State Region
        if hasattr(self, "empty_state_frame"):
            self.empty_state_frame.configure(bg=tokens["app_bg"])
        if hasattr(self, "empty_state_card"):
            self.empty_state_card.configure(bg=tokens["elevated_surface"], highlightbackground=tokens["border"], highlightcolor=tokens["border"])
        if hasattr(self, "lbl_empty_icon"):
            self.lbl_empty_icon.configure(bg=tokens["elevated_surface"])
        if hasattr(self, "lbl_empty_title"):
            self.lbl_empty_title.config(fg=tokens["primary_text"], bg=tokens["elevated_surface"])
        if hasattr(self, "lbl_empty_sub"):
            self.lbl_empty_sub.config(fg=tokens["secondary_text"], bg=tokens["elevated_surface"])
        if hasattr(self, "lbl_empty_formats"):
            self.lbl_empty_formats.config(fg=tokens["secondary_text"], bg=tokens["elevated_surface"])
        if hasattr(self, "lbl_empty_privacy"):
            self.lbl_empty_privacy.config(fg=tokens["secondary_text"], bg=tokens["elevated_surface"])

        # Status Bar Region
        if hasattr(self, "status_bar_frame"):
            self.status_bar_frame.configure(bg=tokens["primary_surface"], highlightbackground=tokens["border"])
        if hasattr(self, "lbl_status_engine"):
            self.lbl_status_engine.config(fg=tokens["primary_text"], bg=tokens["primary_surface"])
        if hasattr(self, "lbl_status_metrics"):
            self.lbl_status_metrics.config(fg=tokens["primary_text"], bg=tokens["primary_surface"])

        # Context Menu
        if hasattr(self, "menu_context"):
            self.menu_context.configure(
                bg=tokens["elevated_surface"],
                fg=tokens["primary_text"],
                activebackground=tokens["accent"],
                activeforeground="#FFFFFF"
            )

        # 2. Text widgets
        for txt in (getattr(self, "txt_roman", None), getattr(self, "txt_urdu", None)):
            if txt:
                txt.configure(
                    bg=tokens["editor_surface"],
                    fg=tokens["primary_text"],
                    insertbackground=tokens["primary_text"],
                    selectbackground=tokens["select_bg"],
                    selectforeground="#FFFFFF" if is_dark else tokens["primary_text"]
                )
                txt.tag_configure(
                    "active_word",
                    background=tokens["active_word_bg"],
                    foreground=tokens["active_word_fg"],
                    font=("Segoe UI", 11 if txt == self.txt_roman else 13, "bold")
                )
                txt.tag_raise("sel")

        # 3. Waveform Canvas & Inspector Canvas
        if hasattr(self, "canvas_waveform"):
            self.canvas_waveform.configure(bg=tokens["waveform_bg"])
            self._draw_waveform()
        if hasattr(self, "canvas_inspector"):
            self.canvas_inspector.configure(bg=tokens["app_bg"])

        # 4. TTK Styles
        self.style.configure(".", background=tokens["app_bg"], foreground=tokens["primary_text"])
        self.style.configure("TFrame", background=tokens["app_bg"])
        self.style.configure("Surface.TFrame", background=tokens["primary_surface"])
        self.style.configure("Card.TFrame", background=tokens["elevated_surface"])
        self.style.configure("TLabel", background=tokens["app_bg"], foreground=tokens["primary_text"])
        self.style.configure("Card.TLabel", background=tokens["elevated_surface"], foreground=tokens["primary_text"])
        self.style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), background=tokens["app_bg"], foreground=tokens["primary_text"])
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 9), background=tokens["app_bg"], foreground=tokens["secondary_text"])
        self.style.configure("Status.TLabel", font=("Segoe UI", 9, "bold"), background=tokens["app_bg"], foreground=tokens["accent"])

        # PanedWindow & Sash
        self.style.configure("TPanedwindow", background=tokens["app_bg"])
        self.style.configure("Sash", sashthickness=6, background=tokens["border"])

        # Buttons & Tabs - crisp visible boundaries using relief="solid" and borderwidth=1
        btn_bg = tokens.get("btn_bg", tokens["elevated_surface"])
        btn_border = tokens.get("btn_border", tokens["border"])
        btn_hover = tokens.get("btn_hover", tokens["border"])

        # Notebook tabs
        self.style.configure("TNotebook", background=tokens["app_bg"], borderwidth=0)
        self.style.configure("TNotebook.Tab", background=btn_bg, foreground=tokens["primary_text"], padding=(12, 6), bordercolor=tokens["border"], borderwidth=1, relief="solid")
        self.style.map("TNotebook.Tab",
                       background=[("selected", tokens["editor_surface"])],
                       foreground=[("selected", tokens["accent"])],
                       bordercolor=[("selected", tokens["border"])])

        self.style.configure(
            "TButton",
            font=("Segoe UI", 9),
            padding=(10, 5),
            background=btn_bg,
            foreground=tokens["primary_text"],
            bordercolor=btn_border,
            lightcolor=btn_border,
            darkcolor=btn_border,
            borderwidth=1,
            relief="solid"
        )
        self.style.map("TButton",
                       background=[("active", btn_hover), ("disabled", tokens["app_bg"]), ("!disabled", btn_bg)],
                       foreground=[("!disabled", tokens["primary_text"]), ("disabled", tokens["muted_text"])],
                       bordercolor=[("active", tokens["accent"]), ("!disabled", btn_border)],
                       lightcolor=[("active", tokens["accent"]), ("!disabled", btn_border)],
                       darkcolor=[("active", tokens["accent"]), ("!disabled", btn_border)])

        self.style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 9),
            padding=(10, 5),
            background=btn_bg,
            foreground=tokens["primary_text"],
            bordercolor=btn_border,
            lightcolor=btn_border,
            darkcolor=btn_border,
            borderwidth=1,
            relief="solid"
        )
        self.style.map("Secondary.TButton",
                       background=[("active", btn_hover), ("disabled", tokens["app_bg"]), ("!disabled", btn_bg)],
                       foreground=[("!disabled", tokens["primary_text"]), ("disabled", tokens["muted_text"])],
                       bordercolor=[("active", tokens["accent"]), ("!disabled", btn_border)],
                       lightcolor=[("active", tokens["accent"]), ("!disabled", btn_border)],
                       darkcolor=[("active", tokens["accent"]), ("!disabled", btn_border)])

        self.style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 6),
            background=tokens["accent"],
            foreground="#FFFFFF",
            bordercolor=tokens["accent"],
            lightcolor=tokens["accent"],
            darkcolor=tokens["accent"],
            borderwidth=1,
            relief="solid"
        )
        self.style.map("Primary.TButton",
                       background=[("active", tokens["accent_hover"]), ("disabled", btn_border), ("!disabled", tokens["accent"])],
                       foreground=[("!disabled", "#FFFFFF"), ("disabled", tokens["muted_text"])],
                       bordercolor=[("active", tokens["accent_hover"]), ("!disabled", tokens["accent"])],
                       lightcolor=[("active", tokens["accent_hover"]), ("!disabled", tokens["accent"])],
                       darkcolor=[("active", tokens["accent_hover"]), ("!disabled", tokens["accent"])])

        self.style.configure(
            "Success.TButton",
            font=("Segoe UI", 9, "bold"),
            padding=(10, 5),
            background=tokens["success"],
            foreground="#FFFFFF",
            bordercolor=tokens["success"],
            lightcolor=tokens["success"],
            darkcolor=tokens["success"],
            borderwidth=1,
            relief="solid"
        )
        self.style.map("Success.TButton",
                       background=[("active", "#157347" if not is_dark else "#229c69"), ("disabled", btn_border)],
                       foreground=[("!disabled", "#FFFFFF")],
                       bordercolor=[("!disabled", tokens["success"])],
                       lightcolor=[("!disabled", tokens["success"])],
                       darkcolor=[("!disabled", tokens["success"])])

        self.style.configure(
            "Warning.TButton",
            font=("Segoe UI", 9, "bold"),
            padding=(10, 5),
            background=tokens["warning"],
            foreground="#FFFFFF",
            bordercolor=tokens["warning"],
            lightcolor=tokens["warning"],
            darkcolor=tokens["warning"],
            borderwidth=1,
            relief="solid"
        )
        self.style.map("Warning.TButton",
                       background=[("active", "#b45309" if not is_dark else "#c9892c"), ("disabled", btn_border)],
                       foreground=[("!disabled", "#FFFFFF")],
                       bordercolor=[("!disabled", tokens["warning"])],
                       lightcolor=[("!disabled", tokens["warning"])],
                       darkcolor=[("!disabled", tokens["warning"])])

        self.style.configure(
            "Danger.TButton",
            font=("Segoe UI", 9),
            padding=(10, 5),
            background=tokens["error"],
            foreground="#FFFFFF",
            bordercolor=tokens["error"],
            lightcolor=tokens["error"],
            darkcolor=tokens["error"],
            borderwidth=1,
            relief="solid"
        )
        self.style.map("Danger.TButton",
                       background=[("active", "#bb2d3b" if not is_dark else "#be4f54"), ("disabled", btn_border)],
                       foreground=[("!disabled", "#FFFFFF")],
                       bordercolor=[("!disabled", tokens["error"])],
                       lightcolor=[("!disabled", tokens["error"])],
                       darkcolor=[("!disabled", tokens["error"])])

        # Inputs
        self.style.configure(
            "TCombobox",
            fieldbackground=tokens["elevated_surface"],
            background=tokens["elevated_surface"],
            foreground=tokens["primary_text"],
            darkcolor=tokens["border"],
            lightcolor=tokens["border"],
            bordercolor=tokens["border"],
            arrowcolor=tokens["primary_text"]
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", tokens["elevated_surface"])],
            foreground=[("readonly", tokens["primary_text"])],
            arrowcolor=[("readonly", tokens["primary_text"])]
        )
        self.style.configure(
            "TEntry",
            fieldbackground=tokens["elevated_surface"],
            foreground=tokens["primary_text"],
            bordercolor=tokens["border"],
            lightcolor=tokens["border"],
            darkcolor=tokens["border"]
        )

        # Scrollbar
        self.style.configure(
            "TScrollbar",
            background=tokens["elevated_surface"],
            troughcolor=tokens["app_bg"],
            bordercolor=tokens["app_bg"],
            arrowcolor=tokens["secondary_text"],
            lightcolor=tokens["elevated_surface"],
            darkcolor=tokens["elevated_surface"],
            relief="flat"
        )

        # Scale
        self.style.configure(
            "TScale",
            background=tokens["elevated_surface"],
            troughcolor=tokens["border"],
            bordercolor=tokens["border"],
            lightcolor=tokens["border"],
            darkcolor=tokens["border"]
        )

        # Checkbutton & Radiobutton
        self.style.configure("TCheckbutton", background=tokens["elevated_surface"], foreground=tokens["primary_text"])
        self.style.configure("TRadiobutton", background=tokens["elevated_surface"], foreground=tokens["primary_text"])

        # Theme toggle label
        if hasattr(self, "btn_theme"):
            self.btn_theme.config(text="☀️ Light Mode" if is_dark else "🌙 Dark Mode")

        # Update Collapsible sections
        for sec in (getattr(self, "sec_selection", None),
                    getattr(self, "sec_model", None),
                    getattr(self, "sec_tweaks", None),
                    getattr(self, "sec_exports", None)):
            if sec:
                sec.apply_theme(tokens)

        if hasattr(self, "lbl_device_info"):
            self._update_device_badge()

        if hasattr(self, "lbl_device_info"):
            self._update_device_badge()

    def _on_setting_changed(self, event=None):
        config = {
            "theme": getattr(self, "current_theme", "dark"),
            "model_name": self.combo_model.get(),
            "device_mode": self.combo_device.get(),
            "language_mode": self.combo_lang.get(),
            "srt_style": self.combo_srt_style.get(),
        }
        config_manager.save_config(config)
        self._update_device_badge()
        self._update_engine_status_bar()

    def _load_saved_settings(self):
        cfg = config_manager.load_config()

        # 0. Theme
        saved_theme = cfg.get("theme", "dark")
        self._apply_theme(saved_theme)

        # 1. Model
        saved_model = cfg.get("model_name", "")
        if saved_model in self.combo_model["values"]:
            self.combo_model.set(saved_model)
        elif "large-v3" in str(saved_model).lower() and "turbo" not in str(saved_model).lower():
            self.combo_model.current(1)
        elif "urdu-sukhan" in str(saved_model).lower():
            self.combo_model.current(2)
        else:
            self.combo_model.current(0)

        # 2. Device
        saved_device = cfg.get("device_mode", "")
        if saved_device in self.combo_device["values"]:
            self.combo_device.set(saved_device)
        elif str(saved_device).lower().startswith("gpu") or str(saved_device).lower() == "cuda":
            self.combo_device.current(1)
        elif str(saved_device).lower().startswith("cpu"):
            self.combo_device.current(2)
        else:
            self.combo_device.current(0)

        # 3. Language
        saved_lang = cfg.get("language_mode", "")
        if saved_lang in self.combo_lang["values"]:
            self.combo_lang.set(saved_lang)
        else:
            self.combo_lang.current(0)

        # 4. SRT Timing Style
        saved_srt = cfg.get("srt_style", "")
        if saved_srt in self.combo_srt_style["values"]:
            self.combo_srt_style.set(saved_srt)
        else:
            self.combo_srt_style.current(0)

        self.combo_model.bind("<<ComboboxSelected>>", self._on_setting_changed)
        self.combo_device.bind("<<ComboboxSelected>>", self._on_setting_changed)
        self.combo_lang.bind("<<ComboboxSelected>>", self._on_setting_changed)
        self.combo_srt_style.bind("<<ComboboxSelected>>", self._on_setting_changed)

        self._update_device_badge()
        self._update_engine_status_bar()

    def _update_device_badge(self):
        device_choice = self.combo_device.get()
        cuda_status = transcribe_pipeline.get_cuda_status()
        is_dark = getattr(self, "current_theme", "dark") == "dark"

        if cuda_status["cuda_available"]:
            dev_name = cuda_status["device_name"]
            if device_choice.startswith("CPU"):
                self.lbl_device_info.config(
                    text="⚪ CPU Mode forced by user (int8 · 8 threads)",
                    foreground="#94a3b8" if is_dark else "#212529"
                )
            else:
                self.lbl_device_info.config(
                    text=f"🟢 CUDA Active: {dev_name} (float16)",
                    foreground="#34d399" if is_dark else "#059669"
                )
        else:
            if device_choice.startswith("GPU") or "Force CUDA" in device_choice:
                self.lbl_device_info.config(
                    text="⚠️ CUDA forced (no CUDA GPU detected; falls back to CPU)",
                    foreground="#fbbf24" if is_dark else "#d97706"
                )
            else:
                self.lbl_device_info.config(
                    text="⚪ CPU Mode active (8 threads · int8)",
                    foreground="#94a3b8" if is_dark else "#212529"
                )

    def _on_preferences_saved(self):
        urdu_content = self.txt_urdu.get("1.0", tk.END).strip()
        if urdu_content:
            if messagebox.askyesno("Update Roman Transcript?",
                                   "Spelling preferences were updated.\nWould you like to re-transliterate the current transcript with the new preferences?",
                                   parent=self.root):
                new_roman = cleanup.clean_roman_text(roman_urdu.transliterate(urdu_content))
                self.txt_roman.delete("1.0", tk.END)
                self.txt_roman.insert("1.0", new_roman)
                self._update_counts()
                self._rebuild_word_spans()

    def _fix_selected_word(self):
        active_tab = self.notebook.index(self.notebook.select())
        txt_widget = self.txt_roman if active_tab == 0 else self.txt_urdu
        is_urdu = (active_tab == 1)

        selected_text = ""
        sel_range = None
        context_snippet = ""

        try:
            ranges = txt_widget.tag_ranges("sel")
            if ranges and len(ranges) >= 2:
                s_idx = txt_widget.index(ranges[0])
                e_idx = txt_widget.index(ranges[1])
                candidate = txt_widget.get(s_idx, e_idx).strip()
                if candidate:
                    selected_text = candidate
                    sel_range = (s_idx, e_idx)
        except tk.TclError:
            pass

        if not selected_text:
            try:
                cursor_idx = txt_widget.index(tk.INSERT)
                w_start = txt_widget.index(f"{cursor_idx} wordstart")
                w_end = txt_widget.index(f"{cursor_idx} wordend")
                candidate = txt_widget.get(w_start, w_end).strip()
                if candidate:
                    selected_text = candidate
                    sel_range = (w_start, w_end)
            except tk.TclError:
                pass

        if sel_range:
            try:
                s_idx, e_idx = sel_range
                ctx_start = txt_widget.index(f"{s_idx} - 25 chars")
                ctx_end = txt_widget.index(f"{e_idx} + 25 chars")
                raw_ctx = txt_widget.get(ctx_start, ctx_end).replace("\n", " ").strip()
                context_snippet = raw_ctx
            except Exception:
                pass

        WordFixDialog(
            self.root,
            initial_word=selected_text,
            is_urdu_tab=is_urdu,
            has_selection=(sel_range is not None),
            selection_range=sel_range,
            context_snippet=context_snippet,
            on_fixed_callback=self._on_word_fixed
        )

    def _on_word_fixed(self, wrong: str, right: str, save_to_lib: bool, scope: str, is_urdu: bool, sel_range: tuple = None):
        active_tab = self.notebook.index(self.notebook.select())
        txt_widget = self.txt_roman if active_tab == 0 else self.txt_urdu

        content = txt_widget.get("1.0", tk.END)
        matches = 0
        timing_str = ""

        if scope == "selected" and sel_range:
            s_idx, e_idx = sel_range
            prefix_text = txt_widget.get("1.0", s_idx)
            word_idx = len(prefix_text.split())

            txt_widget.delete(s_idx, e_idx)
            txt_widget.insert(s_idx, right)
            matches = 1

            base_timed = self.timed_words_roman if active_tab == 0 else self.timed_words_urdu
            if base_timed and 0 <= word_idx < len(base_timed):
                t_item = base_timed[word_idx]
                timing_str = f" [{transcribe_pipeline.srt_time(t_item['start'])} --> {transcribe_pipeline.srt_time(t_item['end'])}]"
        else:
            pattern = re.compile(r"\b" + re.escape(wrong) + r"\b", re.IGNORECASE if not is_urdu else 0)
            matches = len(pattern.findall(content))
            if matches == 0:
                pattern = re.compile(re.escape(wrong), re.IGNORECASE if not is_urdu else 0)
                matches = len(pattern.findall(content))
            new_content = pattern.sub(right, content)
            txt_widget.delete("1.0", tk.END)
            txt_widget.insert("1.0", new_content.strip())

        if is_urdu:
            txt_widget.tag_add("rtl", "1.0", tk.END)
        self._update_counts()

        self._recalibrate_and_sync_subtitles()
        self._rebuild_word_spans()

        if save_to_lib:
            prefs = roman_urdu.get_preferences()
            rule_key = wrong if is_urdu else wrong.lower()
            prefs[rule_key] = right
            roman_urdu.save_preferences(prefs)
            self.lbl_info_status.config(text=f"Fixed '{wrong}' → '{right}'{timing_str} (Saved to Library)")
            messagebox.showinfo(
                "Saved to Library",
                f"Successfully fixed in current transcript{timing_str} and saved rule:\n\n'{wrong}' → '{right}'\n\nAll future transcriptions will now automatically apply this correction.",
                parent=self.root
            )
        else:
            scope_desc = "Single Selected Word" if scope == "selected" else f"All {matches} Occurrences"
            self.lbl_info_status.config(text=f"Fixed '{wrong}' → '{right}' ({scope_desc}){timing_str}")

    def _recalibrate_and_sync_subtitles(self):
        """Regenerates synchronized SRT subtitle files with recalibrated timestamps after any text modification."""
        try:
            stem = self._get_current_stem()
            roman_txt = self.txt_roman.get("1.0", tk.END).strip()
            urdu_txt = self.txt_urdu.get("1.0", tk.END).strip()
            max_words = self._get_srt_max_words()

            if roman_txt:
                roman_srt = self._build_synchronized_srt(roman_txt, is_roman=True, max_words_per_cue=max_words)
                if roman_srt:
                    (OUTPUT_DIR / f"{stem}_roman.srt").write_text(roman_srt, encoding="utf-8")
                (OUTPUT_DIR / f"{stem}_roman.txt").write_text(roman_txt + "\n", encoding="utf-8")

            if urdu_txt:
                urdu_srt = self._build_synchronized_srt(urdu_txt, is_roman=False, max_words_per_cue=max_words)
                if urdu_srt:
                    (OUTPUT_DIR / f"{stem}.srt").write_text(urdu_srt, encoding="utf-8")
                (OUTPUT_DIR / f"{stem}.txt").write_text(urdu_txt + "\n", encoding="utf-8")

            self._rebuild_word_spans()
        except Exception as exc:
            print(f"[WARNING] Subtitle recalibration: {exc}")

    def _update_counts(self):
        active_tab = self.notebook.index(self.notebook.select())
        txt_widget = self.txt_roman if active_tab == 0 else self.txt_urdu
        text = txt_widget.get("1.0", tk.END).strip()
        words = len(text.split()) if text else 0
        chars = len(text)
        self.lbl_counts.config(text=f"Words: {words}  •  Characters: {chars}")
        if hasattr(self, "lbl_status_metrics"):
            self.lbl_status_metrics.config(text=f"{words} words  •  {chars} characters")

    def _warn_missing_ffmpeg(self):
        messagebox.showerror(
            "ffmpeg Not Found",
            "ffmpeg is required for audio/video extraction but was not found on your system PATH.\n\n"
            "Please ensure ffmpeg is installed and available in PATH to transcribe video files.",
            parent=self.root
        )

    # ── Synchronized Audio Player & Follow-Along Highlight Engine ─────────────

    def _load_audio_for_playback(self, filepath: Path):
        """Loads media file into AudioPlayer and initializes playback controls & timeline."""
        try:
            self._show_editor_state(filepath)
            success = self.player.load(filepath)
            if success:
                dur = self.player.get_duration()
                self.waveform_peaks = self._compute_waveform_peaks(self.player.audio_data)
                self._draw_waveform()

                self.slider_seek.config(to=dur if dur > 0 else 100.0)
                self.seek_var.set(0.0)
                self.lbl_player_time.config(text=f"00:00.0 / {format_playback_time(dur)}")
                self.btn_play_pause.config(state=tk.NORMAL)
                self.btn_stop.config(state=tk.NORMAL)
                self.btn_rw.config(state=tk.NORMAL)
                self.btn_ff.config(state=tk.NORMAL)

                stem = filepath.stem
                roman_srt_path = OUTPUT_DIR / f"{stem}_roman.srt"
                roman_txt_path = OUTPUT_DIR / f"{stem}_roman.txt"
                urdu_srt_path = OUTPUT_DIR / f"{stem}.srt"
                urdu_txt_path = OUTPUT_DIR / f"{stem}.txt"

                cur_roman = self.txt_roman.get("1.0", tk.END).strip()
                if not cur_roman and (roman_txt_path.exists() or urdu_txt_path.exists()):
                    if roman_txt_path.exists():
                        self.txt_roman.delete("1.0", tk.END)
                        self.txt_roman.insert("1.0", roman_txt_path.read_text(encoding="utf-8").strip())
                    if urdu_txt_path.exists():
                        self.txt_urdu.delete("1.0", tk.END)
                        self.txt_urdu.insert("1.0", urdu_txt_path.read_text(encoding="utf-8").strip(), "rtl")

                    if roman_srt_path.exists():
                        self.timed_words_roman = parse_srt_words(roman_srt_path.read_text(encoding="utf-8"))
                    if urdu_srt_path.exists():
                        self.timed_words_urdu = parse_srt_words(urdu_srt_path.read_text(encoding="utf-8"))

                    self._rebuild_word_spans()
                    self._update_counts()
                    self.lbl_info_status.config(text=f"Transcribed ({len(self.timed_words_roman)} words)")
                else:
                    self._rebuild_word_spans()
                    self.lbl_info_status.config(text="Ready to Transcribe")

                self._update_engine_status_bar()
            else:
                self.btn_play_pause.config(state=tk.DISABLED)
                self.btn_stop.config(state=tk.DISABLED)
                self.btn_rw.config(state=tk.DISABLED)
                self.btn_ff.config(state=tk.DISABLED)
        except Exception as exc:
            print(f"[AudioPlayer] Failed to load audio: {exc}")

    def _extract_raw_word_spans(self, text: str) -> List[tuple]:
        """Returns list of (tk_start_idx, tk_end_idx, word_str) for all non-whitespace tokens."""
        spans = []
        for m in re.finditer(r"\S+", text):
            s_offset = m.start()
            e_offset = m.end()
            s_line = text[:s_offset].count("\n") + 1
            s_col = s_offset - (text.rfind("\n", 0, s_offset) + 1 if "\n" in text[:s_offset] else 0)
            e_line = text[:e_offset].count("\n") + 1
            e_col = e_offset - (text.rfind("\n", 0, e_offset) + 1 if "\n" in text[:e_offset] else 0)
            spans.append((f"{s_line}.{s_col}", f"{e_line}.{e_col}", m.group(0)))
        return spans

    def _align_spans(self, spans: List[tuple], timed_words: List[dict]) -> List[dict]:
        """Aligns extracted text spans with timed_words list using SequenceMatcher."""
        if not spans or not timed_words:
            return []

        span_words = [s[2] for s in spans]
        timed_strs = [tw["word"] for tw in timed_words]
        matcher = difflib.SequenceMatcher(None, timed_strs, span_words)
        aligned = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for k in range(j2 - j1):
                    aligned.append({
                        "word": span_words[j1 + k],
                        "start": timed_words[i1 + k]["start"],
                        "end": timed_words[i1 + k]["end"],
                        "tk_start": spans[j1 + k][0],
                        "tk_end": spans[j1 + k][1],
                    })
            elif tag == "replace":
                t_start = timed_words[i1]["start"]
                t_end = timed_words[i2 - 1]["end"]
                dur = max(0.01, t_end - t_start)
                cnt = j2 - j1
                for k in range(cnt):
                    aligned.append({
                        "word": span_words[j1 + k],
                        "start": t_start + (k * dur / cnt),
                        "end": t_start + ((k + 1) * dur / cnt),
                        "tk_start": spans[j1 + k][0],
                        "tk_end": spans[j1 + k][1],
                    })
            elif tag == "insert":
                t_start = timed_words[i1 - 1]["end"] if i1 > 0 else timed_words[0]["start"]
                t_end = timed_words[i1]["start"] if i1 < len(timed_words) else (t_start + 0.5)
                dur = max(0.01, t_end - t_start)
                cnt = j2 - j1
                for k in range(cnt):
                    aligned.append({
                        "word": span_words[j1 + k],
                        "start": t_start + (k * dur / cnt),
                        "end": t_start + ((k + 1) * dur / cnt),
                        "tk_start": spans[j1 + k][0],
                        "tk_end": spans[j1 + k][1],
                    })
        return aligned

    def _rebuild_word_spans(self):
        """Builds exact character-level Tkinter text spans aligned to timed_words."""
        try:
            if hasattr(self, "txt_roman") and self.timed_words_roman:
                content_roman = self.txt_roman.get("1.0", "end-1c")
                spans_roman = self._extract_raw_word_spans(content_roman)
                self.aligned_spans_roman = self._align_spans(spans_roman, self.timed_words_roman)
            else:
                self.aligned_spans_roman = []

            if hasattr(self, "txt_urdu") and self.timed_words_urdu:
                content_urdu = self.txt_urdu.get("1.0", "end-1c")
                spans_urdu = self._extract_raw_word_spans(content_urdu)
                self.aligned_spans_urdu = self._align_spans(spans_urdu, self.timed_words_urdu)
            else:
                self.aligned_spans_urdu = []
        except Exception as exc:
            print(f"[WordSpans] Error building word spans: {exc}")

    def _player_tick(self):
        """Periodic UI update for audio playback position, seek slider, and active word highlighting."""
        try:
            if hasattr(self, "player") and self.player.is_playing:
                cur_pos = self.player.get_position()
                total_dur = self.player.get_duration()

                if not self.is_slider_dragging:
                    self.seek_var.set(cur_pos)

                self._update_playhead(cur_pos, total_dur)
                self.lbl_player_time.config(text=f"{format_playback_time(cur_pos)} / {format_playback_time(total_dur)}")

                active_tab = self.notebook.index(self.notebook.select())
                txt_widget = self.txt_roman if active_tab == 0 else self.txt_urdu
                aligned = self.aligned_spans_roman if active_tab == 0 else self.aligned_spans_urdu

                if aligned:
                    active_word = None
                    for item in aligned:
                        if item["start"] <= cur_pos < item["end"]:
                            active_word = item
                            break
                        elif item["start"] > cur_pos:
                            break

                    if active_word is not None and active_word != self.current_highlight_word:
                        txt_widget.tag_remove("active_word", "1.0", tk.END)
                        txt_widget.tag_add("active_word", active_word["tk_start"], active_word["tk_end"])
                        self.current_highlight_word = active_word

                        if self.var_autoscroll.get():
                            txt_widget.see(active_word["tk_start"])
                    elif active_word is None and self.current_highlight_word is not None:
                        txt_widget.tag_remove("active_word", "1.0", tk.END)
                        self.current_highlight_word = None
            else:
                if hasattr(self, "btn_play_pause") and self.btn_play_pause.cget("text") != "▶ Play":
                    self.btn_play_pause.config(text="▶ Play")
                    active_tab = self.notebook.index(self.notebook.select())
                    txt_widget = self.txt_roman if active_tab == 0 else self.txt_urdu
                    txt_widget.tag_remove("active_word", "1.0", tk.END)
                    self.current_highlight_word = None
        except Exception:
            pass
        finally:
            self.root.after(40, self._player_tick)

    def _toggle_play_pause(self):
        """Toggles audio playback between Play and Pause."""
        if not self.player.is_loaded():
            if self.current_filepath and self.current_filepath.is_file():
                self._load_audio_for_playback(self.current_filepath)
            else:
                messagebox.showinfo("Select Media", "Please select a media file to preview.", parent=self.root)
                return

        if self.player.is_playing:
            self.player.pause()
            self.btn_play_pause.config(text="▶ Play")
        else:
            if not self.aligned_spans_roman and not self.aligned_spans_urdu:
                self._rebuild_word_spans()
            success = self.player.play()
            if success:
                self.btn_play_pause.config(text="⏸ Pause")

    def _stop_playback(self):
        """Stops audio playback and rewinds to beginning."""
        self.player.stop()
        self.btn_play_pause.config(text="▶ Play")
        self.seek_var.set(0.0)
        dur = self.player.get_duration()
        self.lbl_player_time.config(text=f"00:00.0 / {format_playback_time(dur)}")
        self._update_playhead(0.0, dur)
        active_tab = self.notebook.index(self.notebook.select())
        txt_widget = self.txt_roman if active_tab == 0 else self.txt_urdu
        txt_widget.tag_remove("active_word", "1.0", tk.END)
        self.current_highlight_word = None

    def _jump_relative(self, seconds: float):
        """Quick jump backward or forward by relative seconds."""
        if not self.player.is_loaded():
            return
        cur = self.player.get_position()
        dur = self.player.get_duration()
        new_pos = max(0.0, min(cur + seconds, dur))
        self.player.seek(new_pos)
        self.seek_var.set(new_pos)
        self._update_playhead(new_pos, dur)
        self.lbl_player_time.config(text=f"{format_playback_time(new_pos)} / {format_playback_time(dur)}")

    def _on_slider_press(self, event):
        """Suppresses timer slider updates while user drags seek slider."""
        self.is_slider_dragging = True

    def _on_slider_release(self, event):
        """Seeks audio to slider position when user releases slider."""
        self.is_slider_dragging = False
        target = self.seek_var.get()
        self.player.seek(target)
        dur = self.player.get_duration()
        self._update_playhead(target, dur)
        self.lbl_player_time.config(text=f"{format_playback_time(target)} / {format_playback_time(dur)}")

    def _on_transcript_click(self, event):
        """Click on any word to seek playback immediately to its timestamp."""
        widget = event.widget
        click_idx = widget.index(f"@{event.x},{event.y}")
        aligned = self.aligned_spans_roman if widget == self.txt_roman else self.aligned_spans_urdu

        for item in aligned:
            if widget.compare(click_idx, ">=", item["tk_start"]) and widget.compare(click_idx, "<=", item["tk_end"]):
                self.player.seek(item["start"])
                cur_pos = item["start"]
                dur = self.player.get_duration()
                self.seek_var.set(cur_pos)
                self._update_playhead(cur_pos, dur)
                self.lbl_player_time.config(text=f"{format_playback_time(cur_pos)} / {format_playback_time(dur)}")

                widget.tag_remove("active_word", "1.0", tk.END)
                widget.tag_add("active_word", item["tk_start"], item["tk_end"])
                self.current_highlight_word = item
                break

    def _on_transcript_double_click(self, event):
        """Double click on any word to seek and immediately start playback."""
        widget = event.widget
        click_idx = widget.index(f"@{event.x},{event.y}")
        aligned = self.aligned_spans_roman if widget == self.txt_roman else self.aligned_spans_urdu

        for item in aligned:
            if widget.compare(click_idx, ">=", item["tk_start"]) and widget.compare(click_idx, "<=", item["tk_end"]):
                self.player.seek(item["start"])
                cur_pos = item["start"]
                dur = self.player.get_duration()
                self.seek_var.set(cur_pos)
                self._update_playhead(cur_pos, dur)
                self.lbl_player_time.config(text=f"{format_playback_time(cur_pos)} / {format_playback_time(dur)}")

                widget.tag_remove("active_word", "1.0", tk.END)
                widget.tag_add("active_word", item["tk_start"], item["tk_end"])
                self.current_highlight_word = item

                if not self.player.is_playing:
                    self.player.play()
                    self.btn_play_pause.config(text="⏸ Pause")
                return "break"

    def _on_tab_changed(self, event=None):
        """Handles switching between Roman Urdu and Urdu Script tabs."""
        self._update_counts()
        active_tab = self.notebook.index(self.notebook.select())
        cur_widget = self.txt_roman if active_tab == 0 else self.txt_urdu
        other_widget = self.txt_urdu if active_tab == 0 else self.txt_roman

        other_widget.tag_remove("active_word", "1.0", tk.END)

        if hasattr(self, "player") and self.player.is_loaded():
            cur_pos = self.player.get_position()
            aligned = self.aligned_spans_roman if active_tab == 0 else self.aligned_spans_urdu
            for item in aligned:
                if item["start"] <= cur_pos < item["end"]:
                    cur_widget.tag_add("active_word", item["tk_start"], item["tk_end"])
                    self.current_highlight_word = item
                    if self.var_autoscroll.get():
                        cur_widget.see(item["tk_start"])
                    break

    def _on_window_close(self):
        """Cleanly releases audio resources upon application shutdown."""
        try:
            if hasattr(self, "player") and self.player:
                self.player.close()
        except Exception:
            pass
        self.root.destroy()

    # ── Background Worker & Transcription ────────────────────────────────────

    def _start_transcription(self):
        if not self.current_filepath or not self.current_filepath.exists():
            messagebox.showwarning("File Required", "Please select a valid media file to transcribe.", parent=self.root)
            return

        self.is_transcribing = True
        self.cancel_flag.clear()

        # Stop any active audio playback before starting transcription
        if hasattr(self, "player") and self.player.is_playing:
            self.player.pause()
            self.btn_play_pause.config(text="▶ Play")

        # UI State updates
        self.btn_start.config(state=tk.DISABLED, text="Transcribing...")
        self.btn_cancel.config(state=tk.NORMAL)
        self.prog_bar.pack(side=tk.LEFT, padx=(10, 0))
        self.prog_bar.start(10)
        self.timer_start = time.time()
        self._update_timer()

        # Determine language choice
        choice = self.combo_lang.get()
        if "Pure English" in choice:
            lang_mode = "en"
        elif "Urdu + English Mixed" in choice:
            lang_mode = "ur"
        else:
            lang_mode = "auto"

        # Determine model choice
        model_choice = self.combo_model.get()
        if "urdu-sukhan-asr-v1" in model_choice:
            selected_model = "Loudness-ai/urdu-sukhan-asr-v1"
        elif "1550M" in model_choice or ("large-v3" in model_choice.lower() and "turbo" not in model_choice.lower()):
            selected_model = "large-v3"
        else:
            selected_model = "large-v3-turbo"

        # Determine device choice
        device_choice = self.combo_device.get()
        if device_choice.startswith("GPU") or "Force CUDA" in device_choice:
            device_mode = "cuda"
        elif device_choice.startswith("CPU"):
            device_mode = "cpu"
        else:
            device_mode = "auto"

        worker = threading.Thread(
            target=self._transcribe_worker,
            args=(self.current_filepath, lang_mode, selected_model, device_mode),
            daemon=True
        )
        worker.start()

    def _cancel_transcription(self):
        if self.is_transcribing:
            self.cancel_flag.set()
            self.lbl_info_status.config(text="Cancelling...")
            self.btn_cancel.config(state=tk.DISABLED)

    def _update_timer(self):
        if self.is_transcribing:
            spinner = self._spinner_chars[self._spinner_idx % len(self._spinner_chars)]
            self._spinner_idx += 1
            if hasattr(self, "lbl_busy_badge"):
                self.lbl_busy_badge.config(text=f" [ {spinner} BUSY ] ", fg="#f59e0b")
            self.root.after(200, self._update_timer)

    def _transcribe_worker(self, input_path: Path, lang_mode: str, model_name: str, device_mode: str = "auto"):
        global _CACHED_MODEL, _CACHED_MODEL_NAME, _CACHED_MODEL_DEVICE

        tmp_dir = None
        try:
            self._set_status("Extracting audio from file via ffmpeg...")
            tmp_dir = tempfile.mkdtemp()
            wav_path = Path(tmp_dir) / f"{input_path.stem}_audio.wav"
            transcribe_pipeline.extract_audio(input_path, wav_path)

            if self.cancel_flag.is_set():
                self.root.after(0, lambda: self._on_worker_complete(cancelled=True))
                return

            resolved_device, resolved_compute, _ = transcribe_pipeline.resolve_device(device_mode)
            model_key = f"{model_name}_{resolved_device}_{resolved_compute}"

            if _CACHED_MODEL is None or _CACHED_MODEL_NAME != model_key:
                dev_label = "CUDA GPU" if resolved_device == "cuda" else f"CPU ({transcribe_pipeline.CPU_THREADS} threads)"
                self._set_status(f"Loading {model_name} on {dev_label}...")
                _CACHED_MODEL = transcribe_pipeline.load_model(model_name, device=device_mode)
                _CACHED_MODEL_NAME = model_key
                _CACHED_MODEL_DEVICE = resolved_device

            model = _CACHED_MODEL

            if self.cancel_flag.is_set():
                self.root.after(0, lambda: self._on_worker_complete(cancelled=True))
                return

            self._set_status("Transcribing speech with Whisper...")

            def progress_cb(prog):
                if self.cancel_flag.is_set():
                    return
                pct = prog.get("progress_pct", 0.0)
                speed = prog.get("speed_factor", 1.0)
                eta = prog.get("eta_seconds", 0.0)
                def _update():
                    if hasattr(self, "lbl_timer") and self.is_transcribing:
                        elapsed = time.time() - self.timer_start
                        self.lbl_timer.config(
                            text=f"Elapsed: {format_time(elapsed)} • {pct:.0f}% ({speed:.1f}x • ~{int(eta)}s left)"
                        )
                self.root.after(0, _update)

            raw_segments, info = transcribe_pipeline.run_transcription(
                model,
                wav_path,
                language=lang_mode,
                beam_size=1,
                vad_filter=True,
                word_timestamps=True,
                progress_callback=progress_cb
            )

            if self.cancel_flag.is_set():
                self.root.after(0, lambda: self._on_worker_complete(cancelled=True))
                return

            self._set_status("Cleaning up transcript...")
            cleaned_segments = cleanup.clean_segments(raw_segments)
            urdu_raw_text = " ".join(s.text.strip() for s in cleaned_segments).strip()
            urdu_text = cleanup.clean_urdu_text(urdu_raw_text)

            is_urdu = (getattr(info, "language", "") == "ur") or ("ur" in lang_mode)

            stem = input_path.stem
            txt_path = OUTPUT_DIR / f"{stem}.txt"
            srt_path = OUTPUT_DIR / f"{stem}.srt"
            roman_txt_path = OUTPUT_DIR / f"{stem}_roman.txt"
            roman_srt_path = OUTPUT_DIR / f"{stem}_roman.srt"

            if is_urdu:
                self._set_status("Generating Roman Urdu transliteration...")
                raw_roman = roman_urdu.transliterate(urdu_text)
                roman_text = cleanup.clean_roman_text(raw_roman)

                # Save all 4 outputs
                txt_path.write_text(urdu_text + "\n", encoding="utf-8")
                transcribe_pipeline.write_srt(cleaned_segments, srt_path)

                roman_txt_path.write_text(roman_text + "\n", encoding="utf-8")
                raw_roman_srt = roman_urdu.transliterate_srt(srt_path.read_text(encoding="utf-8"))
                clean_roman_srt = cleanup.clean_roman_text_in_srt(raw_roman_srt)
                roman_srt_path.write_text(clean_roman_srt, encoding="utf-8")
            else:
                roman_text = urdu_text
                txt_path.write_text(urdu_text + "\n", encoding="utf-8")
                transcribe_pipeline.write_srt(cleaned_segments, srt_path)

            self.root.after(
                0,
                lambda: self._on_transcribe_success(
                    cleaned_segments, info, urdu_text, roman_text, is_urdu
                )
            )

        except Exception as exc:
            err_msg = str(exc)
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda msg=err_msg: self._on_worker_error(msg))
        finally:
            if tmp_dir and os.path.exists(tmp_dir):
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                except Exception:
                    pass

    def _set_status(self, text: str):
        self.root.after(0, lambda: self.lbl_info_status.config(text=text))

    def _on_transcribe_success(self, segments, info, urdu_text, roman_text, is_urdu):
        self.is_transcribing = False
        self.current_segments = segments
        self.current_info = info
        self.raw_urdu_text = urdu_text
        self.raw_roman_text = roman_text

        # Populate synchronized word-level timestamp structures
        self.timed_words_urdu = []
        self.timed_words_roman = []
        for s in (segments or []):
            words = getattr(s, "words", None) or []
            if words:
                for w in words:
                    w_text = getattr(w, "word", "").strip()
                    if not w_text:
                        continue
                    w_start = getattr(w, "start", s.start)
                    w_end = getattr(w, "end", s.end)
                    self.timed_words_urdu.append({
                        "word": w_text,
                        "start": w_start,
                        "end": w_end
                    })
                    r_word = roman_urdu.transliterate_word(w_text).strip()
                    self.timed_words_roman.append({
                        "word": r_word,
                        "start": w_start,
                        "end": w_end
                    })
            else:
                seg_urdu_words = s.text.strip().split()
                if seg_urdu_words:
                    dur = max(0.05, s.end - s.start)
                    count = len(seg_urdu_words)
                    for idx, uw in enumerate(seg_urdu_words):
                        w_start = s.start + (idx * dur / count)
                        w_end = s.start + ((idx + 1) * dur / count)
                        self.timed_words_urdu.append({"word": uw, "start": w_start, "end": w_end})
                        r_word = roman_urdu.transliterate_word(uw).strip()
                        self.timed_words_roman.append({"word": r_word, "start": w_start, "end": w_end})

        self.prog_bar.stop()
        self.prog_bar.pack_forget()
        self.btn_start.config(state=tk.NORMAL, text="✓ Transcribed")
        self.btn_cancel.config(state=tk.DISABLED)

        tokens = THEME_TOKENS.get(getattr(self, "current_theme", "dark"), THEME_TOKENS["dark"])
        is_dark = (getattr(self, "current_theme", "dark") == "dark")
        if is_dark:
            self.lbl_busy_badge.config(text=" [ ● READY ] ", fg="#10b981", bg=tokens["elevated_surface"])
        else:
            self.lbl_busy_badge.config(text=" [ ● READY ] ", fg="#0f5132", bg="#d1e7dd")

        self.lbl_timer.config(text="")

        # Populate Roman Urdu Tab
        self.txt_roman.delete("1.0", tk.END)
        self.txt_roman.insert("1.0", roman_text)

        # Populate Urdu Script Tab
        self.txt_urdu.delete("1.0", tk.END)
        self.txt_urdu.insert("1.0", urdu_text, "rtl")

        elapsed = time.time() - self.timer_start
        lang = getattr(info, "language", "ur")
        prob = getattr(info, "language_probability", 1.0) or 1.0
        self.lbl_info_status.config(
            text=f"Completed in {format_time(elapsed)}  •  Detected: {lang} ({prob:.2f})"
        )
        self._update_counts()

        # Build word spans for synchronized audio follow-along
        self._rebuild_word_spans()

        # Load media for audio playback
        if self.current_filepath and self.current_filepath.exists():
            self._load_audio_for_playback(self.current_filepath)

        # Switch to Roman Urdu by default
        self.notebook.select(0)

    def _on_worker_complete(self, cancelled=False):
        self.is_transcribing = False
        self.prog_bar.stop()
        self.prog_bar.pack_forget()
        self.btn_start.config(state=tk.NORMAL, text="▶ Transcribe Audio")
        self.btn_cancel.config(state=tk.DISABLED)

        tokens = THEME_TOKENS.get(getattr(self, "current_theme", "dark"), THEME_TOKENS["dark"])
        is_dark = (getattr(self, "current_theme", "dark") == "dark")
        if is_dark:
            self.lbl_busy_badge.config(text=" [ ● READY ] ", fg="#10b981", bg=tokens["elevated_surface"])
        else:
            self.lbl_busy_badge.config(text=" [ ● READY ] ", fg="#0f5132", bg="#d1e7dd")

        self.lbl_timer.config(text="")
        if cancelled:
            self.lbl_info_status.config(text="Transcription cancelled.")

    def _on_worker_error(self, err_msg: str):
        self.is_transcribing = False
        self.prog_bar.stop()
        self.prog_bar.pack_forget()
        self.btn_start.config(state=tk.NORMAL, text="▶ Transcribe Audio")
        self.btn_cancel.config(state=tk.DISABLED)

        tokens = THEME_TOKENS.get(getattr(self, "current_theme", "dark"), THEME_TOKENS["dark"])
        is_dark = (getattr(self, "current_theme", "dark") == "dark")
        if is_dark:
            self.lbl_busy_badge.config(text=" [ ● READY ] ", fg="#10b981", bg=tokens["elevated_surface"])
        else:
            self.lbl_busy_badge.config(text=" [ ● READY ] ", fg="#0f5132", bg="#d1e7dd")

        self.lbl_timer.config(text="")
        self.lbl_info_status.config(text="Error occurred during transcription.")
        messagebox.showerror("Transcription Error", f"An error occurred:\n\n{err_msg}", parent=self.root)

    # ── Output Tweaks & Cleanups ─────────────────────────────────────────────

    def _apply_casing(self):
        active_tab = self.notebook.index(self.notebook.select())
        if active_tab == 1:
            messagebox.showinfo("Casing Not Applicable", "Urdu script does not use letter casing.", parent=self.root)
            return

        txt_widget = self.txt_roman
        content = txt_widget.get("1.0", tk.END).strip()
        if not content:
            return

        sentences = re.split(r"([.?!]\s+)", content)
        result = []
        for s in sentences:
            if s and not re.match(r"^[.?!]\s+$", s):
                result.append(s[0].upper() + s[1:] if len(s) > 1 else s.upper())
            else:
                result.append(s)
        new_content = "".join(result)

        txt_widget.delete("1.0", tk.END)
        txt_widget.insert("1.0", new_content)
        self._update_counts()
        self._recalibrate_and_sync_subtitles()
        self.lbl_info_status.config(text="Applied sentence capitalization to Roman Urdu transcript.")

    def _strip_punctuation(self):
        active_tab = self.notebook.index(self.notebook.select())
        txt_widget = self.txt_roman if active_tab == 0 else self.txt_urdu
        content = txt_widget.get("1.0", tk.END).strip()
        if not content:
            return

        cleaned = re.sub(r"[,;:\.?!۔؟\-\"\'\(\)\[\]]", " ", content)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        txt_widget.delete("1.0", tk.END)
        txt_widget.insert("1.0", cleaned)
        if active_tab == 1:
            txt_widget.tag_add("rtl", "1.0", tk.END)
        self._update_counts()
        self._recalibrate_and_sync_subtitles()
        self.lbl_info_status.config(text="Stripped punctuation from active tab.")

    def _remove_punctuation(self):
        self._strip_punctuation()

    def _retransliterate_roman(self):
        urdu_content = self.txt_urdu.get("1.0", tk.END).strip()
        if not urdu_content:
            messagebox.showinfo("Re-Transliterate", "The Urdu Script tab is empty. There is nothing to transliterate.", parent=self.root)
            return

        new_roman = cleanup.clean_roman_text(roman_urdu.transliterate(urdu_content))
        self.txt_roman.delete("1.0", tk.END)
        self.txt_roman.insert("1.0", new_roman)
        self.notebook.select(0)
        self._update_counts()
        self._rebuild_word_spans()
        self.lbl_info_status.config(text="Re-transliterated Roman Urdu using current dictionary and spelling preferences.")

    def _find_and_replace(self):
        find_val = self.entry_find.get().strip()
        replace_val = self.entry_replace.get().strip()
        if not find_val:
            messagebox.showinfo("Find & Replace", "Please enter a word or phrase to find.", parent=self.root)
            return

        active_tab = self.notebook.index(self.notebook.select())
        txt_widget = self.txt_roman if active_tab == 0 else self.txt_urdu
        content = txt_widget.get("1.0", tk.END)

        pattern = re.compile(re.escape(find_val), re.IGNORECASE)
        matches = len(pattern.findall(content))
        if matches == 0:
            messagebox.showinfo("Find & Replace", f"No occurrences of '{find_val}' were found in the active tab.", parent=self.root)
            return

        new_content = pattern.sub(replace_val, content)
        txt_widget.delete("1.0", tk.END)
        txt_widget.insert("1.0", new_content.strip())
        if active_tab == 1:
            txt_widget.tag_add("rtl", "1.0", tk.END)
        self._update_counts()
        self._recalibrate_and_sync_subtitles()
        self._rebuild_word_spans()
        self.lbl_info_status.config(text=f"Replaced {matches} occurrence(s) of '{find_val}' with '{replace_val}'.")

    def _copy_active_text(self):
        active_tab = self.notebook.index(self.notebook.select())
        txt_widget = self.txt_roman if active_tab == 0 else self.txt_urdu
        content = txt_widget.get("1.0", tk.END).strip()
        if content:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.lbl_info_status.config(text="Transcript copied to clipboard!")
        else:
            self.lbl_info_status.config(text="Transcript is empty.")

    def _clear_active_text(self):
        active_tab = self.notebook.index(self.notebook.select())
        tab_name = "Roman Urdu" if active_tab == 0 else "Urdu Script"
        if messagebox.askyesno("Clear Transcript", f"Are you sure you want to clear the {tab_name} text box?", parent=self.root):
            txt_widget = self.txt_roman if active_tab == 0 else self.txt_urdu
            txt_widget.delete("1.0", tk.END)
            txt_widget.tag_remove("active_word", "1.0", tk.END)
            if active_tab == 0:
                self.aligned_spans_roman = []
            else:
                self.aligned_spans_urdu = []
            self.current_highlight_word = None
            self._update_counts()
            self.lbl_info_status.config(text=f"Cleared {tab_name} text.")

    # ── Export Handlers ──────────────────────────────────────────────────────

    def _get_current_stem(self) -> str:
        if self.current_filepath:
            return self.current_filepath.stem
        return "transcript"

    def _get_srt_max_words(self) -> int:
        style_choice = self.combo_srt_style.get()
        if "Word-by-word" in style_choice:
            return 1
        elif "Grouped" in style_choice:
            return 3
        elif "Phrase-level" in style_choice:
            return 6
        elif "Sentence" in style_choice:
            return 999
        return 1

    def _export_plain_text(self):
        stem = self._get_current_stem()
        content = self.txt_roman.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("Empty Content", "No Roman Urdu transcript to export.", parent=self.root)
            return

        dest = filedialog.asksaveasfilename(
            title="Export Roman Urdu Text",
            initialdir=str(OUTPUT_DIR),
            initialfile=f"{stem}_roman.txt",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if dest:
            Path(dest).write_text(content + "\n", encoding="utf-8")
            self.lbl_info_status.config(text=f"Exported text to: {Path(dest).name}")

    def _export_subtitles(self):
        stem = self._get_current_stem()
        is_roman = (self.notebook.index(self.notebook.select()) == 0)
        max_words = self._get_srt_max_words()

        edited_text = (self.txt_roman.get("1.0", tk.END) if is_roman else self.txt_urdu.get("1.0", tk.END)).strip()
        if not edited_text:
            messagebox.showwarning("Empty Content", "No transcript content to generate subtitles from.", parent=self.root)
            return

        srt_content = self._build_synchronized_srt(edited_text, is_roman=is_roman, max_words_per_cue=max_words)
        default_name = f"{stem}_roman.srt" if is_roman else f"{stem}.srt"

        dest = filedialog.asksaveasfilename(
            title=f"Export {'Roman Urdu' if is_roman else 'Urdu'} Subtitles",
            initialdir=str(OUTPUT_DIR),
            initialfile=default_name,
            defaultextension=".srt",
            filetypes=[("SubRip Subtitles", "*.srt"), ("All Files", "*.*")]
        )
        if dest:
            Path(dest).write_text(srt_content, encoding="utf-8")
            self.lbl_info_status.config(text=f"Exported subtitles to: {Path(dest).name}")

    def _build_synchronized_srt(self, edited_text: str, is_roman: bool = True, max_words_per_cue: int = 1) -> str:
        """
        Builds a complete SRT string matching edited_text while preserving exact Whisper timestamps.
        Uses SequenceMatcher to cleanly map edits and corrections against original timestamps.
        """
        edited_words = edited_text.split()
        if not edited_words:
            return ""

        base_timed_words = self.timed_words_roman if is_roman else self.timed_words_urdu
        if not base_timed_words:
            all_orig_words = []
            for s in self.current_segments:
                all_orig_words.extend(s.words or [])
            if not all_orig_words:
                if not self.current_segments:
                    return ""
                entries = []
                for idx, s in enumerate(self.current_segments, start=1):
                    entries.append(
                        f"{idx}\n"
                        f"{transcribe_pipeline.srt_time(s.start)} --> {transcribe_pipeline.srt_time(s.end)}\n"
                        f"{s.text}\n"
                    )
                return "\n".join(entries)
            base_timed_words = [{"word": w.word.strip(), "start": w.start, "end": w.end} for w in all_orig_words]

        orig_word_strings = [tw["word"] for tw in base_timed_words]
        matcher = difflib.SequenceMatcher(None, orig_word_strings, edited_words)

        timed_words = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for idx in range(j2 - j1):
                    timed_words.append((
                        edited_words[j1 + idx],
                        base_timed_words[i1 + idx]["start"],
                        base_timed_words[i1 + idx]["end"]
                    ))
            elif tag == "replace":
                t_start = base_timed_words[i1]["start"]
                t_end = base_timed_words[i2 - 1]["end"]
                dur = max(0.01, t_end - t_start)
                count = j2 - j1
                for idx in range(count):
                    w_start = t_start + (idx * dur / count)
                    w_end = t_start + ((idx + 1) * dur / count)
                    timed_words.append((edited_words[j1 + idx], w_start, w_end))
            elif tag == "insert":
                t_start = base_timed_words[i1 - 1]["end"] if i1 > 0 else base_timed_words[0]["start"]
                t_end = base_timed_words[i1]["start"] if i1 < len(base_timed_words) else (t_start + 0.5)
                dur = max(0.01, t_end - t_start)
                count = j2 - j1
                for idx in range(count):
                    w_start = t_start + (idx * dur / count)
                    w_end = t_start + ((idx + 1) * dur / count)
                    timed_words.append((edited_words[j1 + idx], w_start, w_end))

        return format_srt_cues(timed_words, max_words_per_cue=max_words_per_cue)

    def _export_all(self):
        stem = self._get_current_stem()
        roman_txt = self.txt_roman.get("1.0", tk.END).strip()
        urdu_txt = self.txt_urdu.get("1.0", tk.END).strip()

        if not roman_txt and not urdu_txt:
            messagebox.showwarning("Empty Content", "No transcript data to export.", parent=self.root)
            return

        # 1. Plain text files
        (OUTPUT_DIR / f"{stem}.txt").write_text(urdu_txt + "\n", encoding="utf-8")
        (OUTPUT_DIR / f"{stem}_roman.txt").write_text(roman_txt + "\n", encoding="utf-8")

        # 2. Subtitle files
        max_words = self._get_srt_max_words()
        urdu_srt_path = OUTPUT_DIR / f"{stem}.srt"
        if max_words > 1 or urdu_txt != self.raw_urdu_text.strip() or not urdu_srt_path.exists():
            urdu_srt = self._build_synchronized_srt(urdu_txt, is_roman=False, max_words_per_cue=max_words)
            urdu_srt_path.write_text(urdu_srt, encoding="utf-8")

        roman_srt_path = OUTPUT_DIR / f"{stem}_roman.srt"
        if max_words > 1 or roman_txt != self.raw_roman_text.strip() or not roman_srt_path.exists():
            roman_srt = self._build_synchronized_srt(roman_txt, is_roman=True, max_words_per_cue=max_words)
            roman_srt_path.write_text(roman_srt, encoding="utf-8")

        messagebox.showinfo(
            "Export Complete",
            f"Successfully saved all 4 files to:\n{OUTPUT_DIR}\n\n"
            f"• {stem}.txt\n• {stem}.srt\n• {stem}_roman.txt\n• {stem}_roman.srt",
            parent=self.root
        )
        self.lbl_info_status.config(text=f"Exported all 4 files for '{stem}'.")

    def _open_output_folder(self):
        try:
            os.startfile(str(OUTPUT_DIR))
        except Exception as exc:
            messagebox.showerror("Error", f"Could not open output folder:\n{exc}", parent=self.root)


# ════════════════════════════════════════════════════════════════════════════
# APPLICATION ENTRYPOINT
# ════════════════════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    app = TranscribeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
