#!/usr/bin/env python3
"""
Local Speech Studio — Refined UI Prototype (Tkinter)
===================================================
A standalone visual prototype implementing the modern 3-column MacWhisper/Descript
layout with segmented speech paragraph cues, floating capsule audio player,
and contextual inspector panel.
"""

import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# DPI Awareness
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# Refined Studio Color Palette (MacWhisper Style)
PALETTE = {
    "window_bg":        "#121216",
    "sidebar_bg":       "#18181f",
    "canvas_bg":        "#131317",
    "inspector_bg":     "#18181f",
    "card_bg":          "#202028",
    "card_hover":       "#272732",
    "card_active":      "#1c2438",
    "border":           "#2a2a36",
    "border_subtle":    "#22222c",
    "primary_text":     "#f4f4f7",
    "secondary_text":   "#a1a1aa",
    "muted_text":       "#71717a",
    "accent":           "#3b82f6",
    "accent_hover":     "#2563eb",
    "accent_glow":      "#60a5fa",
    "timeline_bar":     "#3b82f6",
    "highlight_bg":     "#f59e0b",
    "highlight_fg":     "#000000",
    "success":          "#10b981",
}

SAMPLE_SEGMENTS_ROMAN = [
    ("00:00.0", "00:03.2", "Speaker 1", "asalam alaikum dear students, I have some exciting news to share with you today."),
    ("00:03.5", "00:06.8", "Speaker 1", "hum ne exam hack sessions karwaya thay jo aap logon ne bohat hi appreciate kiya tha."),
    ("00:07.2", "00:11.4", "Speaker 1", "is dafa hum AFM mein professional marks ki preparation ko aur zyada focused tareeqay se cover karein gay."),
    ("00:12.0", "00:16.5", "Speaker 1", "aap ko har question ka structure aur key requirements detail mein samjhai jaye gi taakay koi issue na aye."),
    ("00:17.1", "00:22.0", "Speaker 1", "is session ki recordings aur transcribed notes aap ko portal par provide kar diye jayen gay."),
]

SAMPLE_SEGMENTS_URDU = [
    ("00:00.0", "00:03.2", "اسپیکر 1", "السلام علیکم عزیز طلباء، آج میرے پاس آپ کے ساتھ شیئر کرنے کے لیے ایک خوشخبری ہے۔"),
    ("00:03.5", "00:06.8", "اسپیکر 1", "ہم نے exam hack سیشنز کروائے تھے جو آپ لوگوں نے بہت ہی سراہے تھے۔"),
    ("00:07.2", "00:11.4", "اسپیکر 1", "اس دفعہ ہم AFM میں پروفیشنل مارکس کی تیاری کو اور زیادہ فوکسڈ طریقے سے کور کریں گے۔"),
    ("00:12.0", "00:16.5", "اسپیکر 1", "آپ کو ہر سوال کا اسٹرکچر اور کلیدی ضروریات تفصیل میں سمجھائی جائیں گی تاکہ کوئی مسئلہ نہ آئے۔"),
    ("00:17.1", "00:22.0", "اسپیکر 1", "اس سیشن کی ریکارڈنگز اور نوٹس آپ کو پورٹل پر مہیا کر دیے جائیں گے۔"),
]


class StudioPrototype(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Local Speech Studio — Refined UI Prototype")
        self.geometry("1200x740+30+20")
        self.minsize(1050, 650)
        self.configure(bg=PALETTE["window_bg"])

        self.current_lang = "roman"  # "roman" or "urdu"
        self.active_segment_idx = 1
        self.is_playing = False

        self._setup_styles()
        self._build_layout()

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Base Frame & PanedWindow styles
        style.configure("Studio.TFrame", background=PALETTE["window_bg"])
        style.configure("Sidebar.TFrame", background=PALETTE["sidebar_bg"])
        style.configure("Canvas.TFrame", background=PALETTE["canvas_bg"])
        style.configure("Inspector.TFrame", background=PALETTE["inspector_bg"])

        # Primary Action Button (Blue Rounded Pill)
        style.configure(
            "PrimaryAction.TButton",
            font=("Segoe UI", 9, "bold"),
            background=PALETTE["accent"],
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(12, 8),
            relief="flat"
        )
        style.map(
            "PrimaryAction.TButton",
            background=[("active", PALETTE["accent_hover"]), ("pressed", "#1d4ed8")]
        )

        # Secondary Button
        style.configure(
            "SecondaryAction.TButton",
            font=("Segoe UI", 9),
            background=PALETTE["card_bg"],
            foreground=PALETTE["primary_text"],
            borderwidth=1,
            bordercolor=PALETTE["border"],
            padding=(10, 6),
            relief="solid"
        )
        style.map(
            "SecondaryAction.TButton",
            background=[("active", PALETTE["card_hover"])]
        )

    def _build_layout(self):
        # Top Window Header Strip
        self.top_bar = tk.Frame(self, bg=PALETTE["sidebar_bg"], height=38, highlightthickness=1, highlightbackground=PALETTE["border_subtle"])
        self.top_bar.pack(fill=tk.X, side=tk.TOP)
        self.top_bar.pack_propagate(False)

        # Left controls & branding
        f_top_left = tk.Frame(self.top_bar, bg=PALETTE["sidebar_bg"])
        f_top_left.pack(side=tk.LEFT, padx=14)

        tk.Label(f_top_left, text="● ● ●", font=("Segoe UI", 8), fg="#ff5f56", bg=PALETTE["sidebar_bg"]).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(f_top_left, text="LOCAL SPEECH STUDIO", font=("Segoe UI", 9, "bold"), fg=PALETTE["secondary_text"], bg=PALETTE["sidebar_bg"]).pack(side=tk.LEFT, padx=(0, 8))
        
        lbl_cuda = tk.Label(f_top_left, text="  ● CUDA Active (float16)  ", font=("Segoe UI", 8, "bold"), fg=PALETTE["success"], bg="#064e3b", padx=6, pady=2)
        lbl_cuda.pack(side=tk.LEFT)

        # Right status
        f_top_right = tk.Frame(self.top_bar, bg=PALETTE["sidebar_bg"])
        f_top_right.pack(side=tk.RIGHT, padx=14)
        tk.Label(f_top_right, text="Whisper Large-v3 Full (1550M)  •  100% Offline", font=("Segoe UI", 8), fg=PALETTE["muted_text"], bg=PALETTE["sidebar_bg"]).pack(side=tk.RIGHT)

        # Main 3-Column Container
        self.studio_body = tk.Frame(self, bg=PALETTE["window_bg"])
        self.studio_body.pack(fill=tk.BOTH, expand=True)

        # Pack order: Sidebar LEFT, Inspector RIGHT, Canvas expands in CENTER
        self._build_sidebar(self.studio_body)
        self._build_inspector(self.studio_body)
        self._build_center_canvas(self.studio_body)

    # =========================================================================
    # 1. LEFT SIDEBAR (LIBRARY & RECENT HISTORY)
    # =========================================================================
    def _build_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg=PALETTE["sidebar_bg"], width=230, highlightthickness=1, highlightbackground=PALETTE["border_subtle"])
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        p = 12
        # Section: Library
        tk.Label(sidebar, text="LIBRARY", font=("Segoe UI", 8, "bold"), fg=PALETTE["muted_text"], bg=PALETTE["sidebar_bg"]).pack(anchor=tk.W, padx=p, pady=(16, 6))

        btn_new = tk.Label(sidebar, text="  🏠  Open New Media...  ", font=("Segoe UI", 9), fg=PALETTE["secondary_text"], bg=PALETTE["sidebar_bg"], cursor="hand2", anchor=tk.W, pady=6, padx=8)
        btn_new.pack(fill=tk.X, padx=8)

        f_active = tk.Frame(sidebar, bg=PALETTE["card_bg"], highlightthickness=1, highlightbackground=PALETTE["border"], padx=8, pady=6)
        f_active.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(f_active, text="📄  lecture_part1.mp4", font=("Segoe UI", 9, "bold"), fg=PALETTE["primary_text"], bg=PALETTE["card_bg"]).pack(anchor=tk.W)
        tk.Label(f_active, text="00:57.4  •  177 words", font=("Segoe UI", 8), fg=PALETTE["accent_glow"], bg=PALETTE["card_bg"]).pack(anchor=tk.W)

        # Section: Recent History
        tk.Label(sidebar, text="RECENT TRANSCRIPTS", font=("Segoe UI", 8, "bold"), fg=PALETTE["muted_text"], bg=PALETTE["sidebar_bg"]).pack(anchor=tk.W, padx=p, pady=(16, 6))

        recents = ["Sir Asad Exam Hack", "AFM Exam Review", "Sir Hammad Promo", "FM Intro Roman"]
        for r in recents:
            lbl_r = tk.Label(sidebar, text=f"  🎙️  {r}", font=("Segoe UI", 8), fg=PALETTE["secondary_text"], bg=PALETTE["sidebar_bg"], anchor=tk.W, cursor="hand2", pady=4, padx=8)
            lbl_r.pack(fill=tk.X, padx=8)

        # Bottom Hardware Card
        f_hw = tk.Frame(sidebar, bg=PALETTE["card_bg"], highlightthickness=1, highlightbackground=PALETTE["border"], padx=10, pady=10)
        f_hw.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=12)

        tk.Label(f_hw, text="⚡ GPU ACCELERATION", font=("Segoe UI", 8, "bold"), fg=PALETTE["primary_text"], bg=PALETTE["card_bg"]).pack(anchor=tk.W)
        tk.Label(f_hw, text="NVIDIA RTX 3080", font=("Segoe UI", 9, "bold"), fg=PALETTE["success"], bg=PALETTE["card_bg"]).pack(anchor=tk.W, pady=(2, 0))
        tk.Label(f_hw, text="10.0 GB VRAM  •  float16", font=("Segoe UI", 8), fg=PALETTE["muted_text"], bg=PALETTE["card_bg"]).pack(anchor=tk.W)

    # =========================================================================
    # 2. CENTER SPEECH CANVAS & FLOATING CAPSULE PLAYER
    # =========================================================================
    def _build_center_canvas(self, parent):
        self.canvas_container = tk.Frame(parent, bg=PALETTE["canvas_bg"])
        self.canvas_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Header Bar of Center Canvas
        f_hdr = tk.Frame(self.canvas_container, bg=PALETTE["canvas_bg"], height=48, highlightthickness=1, highlightbackground=PALETTE["border_subtle"])
        f_hdr.pack(fill=tk.X, side=tk.TOP)
        f_hdr.pack_propagate(False)

        # Title
        tk.Label(f_hdr, text="lecture_part1.mp4", font=("Segoe UI", 11, "bold"), fg=PALETTE["primary_text"], bg=PALETTE["canvas_bg"]).pack(side=tk.LEFT, padx=18)

        # Language Pill Switcher
        f_pill = tk.Frame(f_hdr, bg=PALETTE["card_bg"], highlightthickness=1, highlightbackground=PALETTE["border"], padx=2, pady=2)
        f_pill.pack(side=tk.LEFT, padx=14)

        self.btn_lang_roman = tk.Label(
            f_pill, text="  🔤 Roman Urdu  ", font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF", bg=PALETTE["accent"], cursor="hand2", padx=6, pady=3
        )
        self.btn_lang_roman.pack(side=tk.LEFT)
        self.btn_lang_roman.bind("<Button-1>", lambda e: self._switch_lang("roman"))

        self.btn_lang_urdu = tk.Label(
            f_pill, text="  ✍️ Urdu Script (RTL)  ", font=("Segoe UI", 9),
            fg=PALETTE["secondary_text"], bg=PALETTE["card_bg"], cursor="hand2", padx=6, pady=3
        )
        self.btn_lang_urdu.pack(side=tk.LEFT)
        self.btn_lang_urdu.bind("<Button-1>", lambda e: self._switch_lang("urdu"))

        # Right quick tool buttons
        f_tools = tk.Frame(f_hdr, bg=PALETTE["canvas_bg"])
        f_tools.pack(side=tk.RIGHT, padx=16)

        btn_search = tk.Label(f_tools, text=" 🔍 Search ", font=("Segoe UI", 9), fg=PALETTE["secondary_text"], bg=PALETTE["card_bg"], highlightthickness=1, highlightbackground=PALETTE["border"], padx=8, pady=4, cursor="hand2")
        btn_search.pack(side=tk.LEFT, padx=4)

        btn_export = tk.Label(f_tools, text=" 📤 Export ", font=("Segoe UI", 9), fg=PALETTE["secondary_text"], bg=PALETTE["card_bg"], highlightthickness=1, highlightbackground=PALETTE["border"], padx=8, pady=4, cursor="hand2")
        btn_export.pack(side=tk.LEFT)

        # Scrollable Segments Area
        self.scroll_canvas = tk.Canvas(self.canvas_container, bg=PALETTE["canvas_bg"], highlightthickness=0)
        self.scroll_canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=(16, 75))

        self.segments_frame = tk.Frame(self.scroll_canvas, bg=PALETTE["canvas_bg"])
        self.canvas_win_id = self.scroll_canvas.create_window((0, 0), window=self.segments_frame, anchor="nw")

        def _on_canvas_configure(event):
            self.scroll_canvas.itemconfig(self.canvas_win_id, width=event.width)
            self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))

        self.scroll_canvas.bind("<Configure>", _on_canvas_configure)
        self.segments_frame.bind("<Configure>", lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all")))

        self._render_segments()

        # Floating Bottom Player Capsule (MacWhisper Style)
        self._build_floating_capsule_player()

    def _render_segments(self):
        for widget in self.segments_frame.winfo_children():
            widget.destroy()

        segments = SAMPLE_SEGMENTS_ROMAN if self.current_lang == "roman" else SAMPLE_SEGMENTS_URDU
        is_rtl = (self.current_lang == "urdu")

        for idx, (start_t, end_t, speaker, text) in enumerate(segments):
            is_active = (idx == self.active_segment_idx)
            row_bg = PALETTE["card_active"] if is_active else PALETTE["canvas_bg"]
            border_col = PALETTE["accent"] if is_active else PALETTE["canvas_bg"]

            f_seg = tk.Frame(self.segments_frame, bg=row_bg, highlightthickness=1, highlightbackground=border_col, padx=12, pady=10)
            f_seg.pack(fill=tk.X, pady=4)

            # Left timestamp gutter
            f_gutter = tk.Frame(f_seg, bg=row_bg, width=85)
            f_gutter.pack(side=tk.LEFT if not is_rtl else tk.RIGHT, anchor="n")

            tk.Label(f_gutter, text=start_t, font=("Segoe UI", 9, "bold"), fg=PALETTE["accent_glow"], bg=row_bg).pack(anchor=tk.E if not is_rtl else tk.W)
            tk.Label(f_gutter, text=speaker, font=("Segoe UI", 8), fg=PALETTE["muted_text"], bg=row_bg).pack(anchor=tk.E if not is_rtl else tk.W)

            # Vertical accent bar
            v_line = tk.Frame(f_seg, bg=PALETTE["timeline_bar"], width=3)
            v_line.pack(side=tk.LEFT if not is_rtl else tk.RIGHT, fill=tk.Y, padx=10)

            # Text content
            font_spec = ("Segoe UI", 11) if not is_rtl else ("Segoe UI", 12)
            lbl_txt = tk.Label(
                f_seg, text=text, font=font_spec, fg=PALETTE["primary_text"],
                bg=row_bg, wraplength=540, justify=tk.LEFT if not is_rtl else tk.RIGHT
            )
            lbl_txt.pack(side=tk.LEFT if not is_rtl else tk.RIGHT, fill=tk.BOTH, expand=True)

    def _switch_lang(self, lang):
        self.current_lang = lang
        if lang == "roman":
            self.btn_lang_roman.config(fg="#FFFFFF", bg=PALETTE["accent"])
            self.btn_lang_urdu.config(fg=PALETTE["secondary_text"], bg=PALETTE["card_bg"])
        else:
            self.btn_lang_urdu.config(fg="#FFFFFF", bg=PALETTE["accent"])
            self.btn_lang_roman.config(fg=PALETTE["secondary_text"], bg=PALETTE["card_bg"])
        self._render_segments()

    def _build_floating_capsule_player(self):
        capsule = tk.Frame(
            self.canvas_container,
            bg="#1c1c26",
            highlightthickness=1,
            highlightbackground="#36364a",
            padx=16,
            pady=8
        )
        capsule.place(relx=0.5, rely=0.90, anchor="center", relwidth=0.92, height=52)
        capsule.lift()

        # Play/Pause
        self.btn_play = tk.Button(
            capsule, text="▶", font=("Segoe UI", 11, "bold"), bg="#FFFFFF", fg="#000000",
            activebackground="#E5E7EB", width=3, relief="flat", cursor="hand2", command=self._toggle_play
        )
        self.btn_play.pack(side=tk.LEFT, padx=(0, 10))

        # Skip buttons
        tk.Button(capsule, text="⏪ -5s", font=("Segoe UI", 8), bg=PALETTE["card_bg"], fg=PALETTE["secondary_text"], relief="flat", cursor="hand2").pack(side=tk.LEFT, padx=3)
        tk.Button(capsule, text="⏩ +5s", font=("Segoe UI", 8), bg=PALETTE["card_bg"], fg=PALETTE["secondary_text"], relief="flat", cursor="hand2").pack(side=tk.LEFT, padx=(0, 12))

        # Scrub Track (Scale)
        self.scale_seek = ttk.Scale(capsule, from_=0, to=57.4, value=4.5)
        self.scale_seek.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))

        # Timecode
        tk.Label(capsule, text="00:04.5 / 00:57.4", font=("Consolas", 9, "bold"), fg=PALETTE["primary_text"], bg=PALETTE["card_bg"]).pack(side=tk.LEFT, padx=(0, 10))

        # Speed pill
        tk.Label(capsule, text=" 1.0x ", font=("Segoe UI", 8, "bold"), fg=PALETTE["accent_glow"], bg=PALETTE["card_hover"], highlightthickness=1, highlightbackground=PALETTE["border"], padx=6, pady=3, cursor="hand2").pack(side=tk.LEFT)

    def _toggle_play(self):
        self.is_playing = not self.is_playing
        self.btn_play.config(text="⏸" if self.is_playing else "▶")

    # =========================================================================
    # 3. RIGHT INSPECTOR PANEL
    # =========================================================================
    def _build_inspector(self, parent):
        inspector = tk.Frame(parent, bg=PALETTE["inspector_bg"], width=280, highlightthickness=1, highlightbackground=PALETTE["border_subtle"])
        inspector.pack(side=tk.RIGHT, fill=tk.Y)
        inspector.pack_propagate(False)

        p = 14
        # Top Primary Actions
        f_top_act = tk.Frame(inspector, bg=PALETTE["inspector_bg"])
        f_top_act.pack(fill=tk.X, padx=p, pady=(16, 12))

        btn_copy = ttk.Button(f_top_act, text="📋  Copy Active Transcript", style="PrimaryAction.TButton")
        btn_copy.pack(fill=tk.X, pady=(0, 6))

        btn_srt = ttk.Button(f_top_act, text="⬇️  Export Subtitles (.SRT)", style="SecondaryAction.TButton")
        btn_srt.pack(fill=tk.X)

        # View Mode Switcher Tiles (MacWhisper Style)
        tk.Label(inspector, text="VIEW FORMAT", font=("Segoe UI", 8, "bold"), fg=PALETTE["muted_text"], bg=PALETTE["inspector_bg"]).pack(anchor=tk.W, padx=p, pady=(6, 6))

        f_tiles = tk.Frame(inspector, bg=PALETTE["inspector_bg"])
        f_tiles.pack(fill=tk.X, padx=p, pady=(0, 12))

        f_t1 = tk.Frame(f_tiles, bg=PALETTE["card_bg"], highlightthickness=1, highlightbackground=PALETTE["border"], padx=8, pady=8, cursor="hand2")
        f_t1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        tk.Label(f_t1, text="📄", font=("Segoe UI", 12), bg=PALETTE["card_bg"]).pack(anchor=tk.W)
        tk.Label(f_t1, text="Full Text", font=("Segoe UI", 8, "bold"), fg=PALETTE["secondary_text"], bg=PALETTE["card_bg"]).pack(anchor=tk.W)

        f_t2 = tk.Frame(f_tiles, bg=PALETTE["card_active"], highlightthickness=2, highlightbackground=PALETTE["accent"], padx=8, pady=8, cursor="hand2")
        f_t2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
        tk.Label(f_t2, text="📑", font=("Segoe UI", 12), bg=PALETTE["card_active"]).pack(anchor=tk.W)
        tk.Label(f_t2, text="Segments", font=("Segoe UI", 8, "bold"), fg=PALETTE["accent_glow"], bg=PALETTE["card_active"]).pack(anchor=tk.W)

        # Surgical Word Fixing Tool
        f_fix = tk.Frame(inspector, bg=PALETTE["card_bg"], highlightthickness=1, highlightbackground=PALETTE["border"], padx=10, pady=10)
        f_fix.pack(fill=tk.X, padx=p, pady=(0, 14))

        tk.Label(f_fix, text="🎯 SURGICAL WORD FIXING", font=("Segoe UI", 8, "bold"), fg=PALETTE["primary_text"], bg=PALETTE["card_bg"]).pack(anchor=tk.W)
        tk.Label(f_fix, text="Active Selection: 'exam hack'", font=("Segoe UI", 8), fg="#fbbf24", bg=PALETTE["card_bg"]).pack(anchor=tk.W, pady=(4, 6))

        e_fix = tk.Entry(f_fix, font=("Segoe UI", 9), bg=PALETTE["sidebar_bg"], fg="#FFFFFF", insertbackground="#FFFFFF", relief="flat", highlightthickness=1, highlightbackground=PALETTE["border"])
        e_fix.insert(0, "Exam Hack")
        e_fix.pack(fill=tk.X, pady=(0, 8))

        f_fix_btns = tk.Frame(f_fix, bg=PALETTE["card_bg"])
        f_fix_btns.pack(fill=tk.X)

        btn_fix_one = tk.Button(f_fix_btns, text="Fix Word", font=("Segoe UI", 8, "bold"), bg=PALETTE["accent"], fg="#FFFFFF", relief="flat", cursor="hand2", padx=8, pady=4)
        btn_fix_one.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))

        btn_fix_all = tk.Button(f_fix_btns, text="Fix All", font=("Segoe UI", 8), bg=PALETTE["card_hover"], fg=PALETTE["secondary_text"], relief="flat", cursor="hand2", padx=8, pady=4)
        btn_fix_all.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))

        # Engine Settings
        tk.Label(inspector, text="ENGINE SETTINGS", font=("Segoe UI", 8, "bold"), fg=PALETTE["muted_text"], bg=PALETTE["inspector_bg"]).pack(anchor=tk.W, padx=p, pady=(0, 6))

        f_eng = tk.Frame(inspector, bg=PALETTE["inspector_bg"])
        f_eng.pack(fill=tk.X, padx=p, pady=(0, 10))

        tk.Label(f_eng, text="Model:", font=("Segoe UI", 8), fg=PALETTE["secondary_text"], bg=PALETTE["inspector_bg"]).pack(anchor=tk.W)
        cb_m = ttk.Combobox(f_eng, values=["Whisper Large-v3 Full (1550M)", "Whisper Large-v3-Turbo (809M)"], state="readonly")
        cb_m.current(0)
        cb_m.pack(fill=tk.X, pady=(2, 6))

        tk.Label(f_eng, text="Compute Device:", font=("Segoe UI", 8), fg=PALETTE["secondary_text"], bg=PALETTE["inspector_bg"]).pack(anchor=tk.W)
        cb_d = ttk.Combobox(f_eng, values=["CUDA GPU (float16)", "CPU Mode (int8)"], state="readonly")
        cb_d.current(0)
        cb_d.pack(fill=tk.X, pady=(2, 0))


if __name__ == "__main__":
    app = StudioPrototype()
    app.mainloop()
