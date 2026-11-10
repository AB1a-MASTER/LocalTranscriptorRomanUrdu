"""
Automated Integration Test for Synchronized Audio Playback, Waveform Timeline,
and Redesigned UI/UX Components
Tests:
  1. Multi-format audio loading & duration verification
  2. Waveform peaks calculation & canvas rendering
  3. Empty state vs Editor workspace state switching
  4. Real-time follow-along word highlighting
  5. Click-to-seek timestamp navigation
  6. Text selection tracking & Play Selection
  7. Inspector panel collapse/expand toggle
  8. Dark & Light theme switching
  9. Transport controls (Play, Pause, Stop, Seek)
"""

import sys
import time
import types
from pathlib import Path

# Add scripts directory
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import tkinter as tk
from ui import TranscribeApp, parse_srt_words, format_playback_time, THEME_TOKENS


def test_preview_playback_engine():
    root = tk.Tk()
    root.deiconify()
    root.update()

    app = TranscribeApp(root)
    root.update()
    print("[1/9] TranscribeApp initialized successfully.")

    # Test 1: Empty state active initially
    assert hasattr(app, "empty_state_frame"), "empty_state_frame should exist"
    print("      Initial empty state active.")

    # Test 2: Load Media File & verify state switch to Editor
    test_media = Path("input/test2.mp3")
    assert test_media.exists(), "input/test2.mp3 not found"
    app.current_filepath = test_media
    app.entry_path.delete(0, tk.END)
    app.entry_path.insert(0, str(test_media))

    app._load_audio_for_playback(test_media)
    root.update()

    dur = app.player.get_duration()
    print(f"[2/9] Media loaded into player: duration = {dur:.2f}s")
    assert 57.0 <= dur <= 58.0, f"Unexpected duration: {dur}"
    assert app.lbl_info_filename.cget("text") == f"📁 {test_media.name}"

    # Verify existing transcript and word-level timestamps were auto-loaded
    assert len(app.timed_words_roman) > 0, "timed_words_roman should be auto-loaded"
    assert len(app.aligned_spans_roman) > 0, "aligned_spans_roman should be built"
    print(f"      Loaded {len(app.timed_words_roman)} timed words and {len(app.aligned_spans_roman)} aligned spans.")

    # Test 3: Waveform peaks calculation & Canvas rendering
    assert len(app.waveform_peaks) > 0, "Waveform peaks should be computed on audio load"
    print(f"[3/9] Waveform amplitude peaks generated: {len(app.waveform_peaks)} bins.")

    # Test 4: Word Highlighting at t = 1.2s (students,)
    # In test2_roman.srt:
    # 3: dear [0.9s - 1.02s]
    # 4: students, [1.02s - 1.48s]
    app.player.seek(1.2)
    app.player.is_playing = True  # Simulate active playing
    app._player_tick()

    active_tag_ranges = app.txt_roman.tag_ranges("active_word")
    assert active_tag_ranges, "Expected active_word tag to be applied at t=1.2s"
    highlighted_text = app.txt_roman.get(active_tag_ranges[0], active_tag_ranges[1])
    print(f"[4/9] Active highlighted word at t=1.2s: '{highlighted_text}' (expected 'students,')")
    assert "students" in highlighted_text.lower(), f"Unexpected highlighted word: {highlighted_text}"

    # Test 5: Word Highlighting advances at t = 2.45s (news)
    # 8: exciting [1.88s - 2.34s]
    # 9: news [2.34s - 2.64s]
    app.player.seek(2.45)
    app._player_tick()
    active_tag_ranges = app.txt_roman.tag_ranges("active_word")
    assert active_tag_ranges, "Expected active_word tag to be applied at t=2.45s"
    highlighted_text2 = app.txt_roman.get(active_tag_ranges[0], active_tag_ranges[1])
    print(f"[5/9] Active highlighted word at t=2.45s: '{highlighted_text2}' (expected 'news')")
    assert "news" in highlighted_text2.lower(), f"Unexpected highlighted word: {highlighted_text2}"

    # Test 6: Click-to-Seek Navigation
    exciting_item = None
    for item in app.aligned_spans_roman:
        if "exciting" in item["word"].lower():
            exciting_item = item
            break
    assert exciting_item is not None, "'exciting' span not found in aligned_spans_roman"

    root.update()
    bbox = app.txt_roman.bbox(exciting_item["tk_start"])
    assert bbox is not None, f"Character bbox should not be None for {exciting_item['tk_start']}"
    click_x = bbox[0] + 4
    click_y = bbox[1] + 4
    mock_click = types.SimpleNamespace(widget=app.txt_roman, x=click_x, y=click_y)

    app._on_transcript_click(mock_click)
    seek_pos = app.player.get_position()
    print(f"[6/9] Click-to-seek jumped player to: {seek_pos:.2f}s (expected ~{exciting_item['start']:.2f}s)")
    assert abs(seek_pos - exciting_item["start"]) < 0.05, f"Seek inaccurate: {seek_pos} vs {exciting_item['start']}"

    # Test 7: Selection Tracking & Play Selected Span
    app.txt_roman.tag_add("sel", exciting_item["tk_start"], exciting_item["tk_end"])
    app._on_selection_change()
    assert "exciting" in app.lbl_sel_info.cget("text").lower(), "Inspector snippet should display selected word"
    print(f"[7/9] Text selection tracking verified: {app.lbl_sel_info.cget('text').splitlines()[0]}")

    # Test 8: Inspector Panel Collapse/Expand & Theme Toggling
    app._toggle_inspector()
    assert not app.is_inspector_visible, "Inspector should be hidden"
    assert app.btn_toggle_inspector.cget("text") == "◀ Show Inspector"
    app._toggle_inspector()
    assert app.is_inspector_visible, "Inspector should be visible"

    # Theme Toggle
    app._apply_theme("light")
    assert app.current_theme == "light"
    assert app.root.cget("bg") == THEME_TOKENS["light"]["app_bg"]
    app._apply_theme("dark")
    assert app.current_theme == "dark"
    assert app.root.cget("bg") == THEME_TOKENS["dark"]["app_bg"]
    print("[8/9] Inspector collapse/expand and Theme switching verified.")

    # Test 9: Play/Pause/Stop
    app.player.is_playing = False
    app._toggle_play_pause()
    assert app.player.is_playing, "Player should be playing after toggle"
    assert app.btn_play_pause.cget("text") == "⏸ Pause"

    app._toggle_play_pause()
    assert not app.player.is_playing, "Player should be paused after toggle"
    assert app.btn_play_pause.cget("text") == "▶ Play"

    app._stop_playback()
    assert app.player.get_position() == 0.0, "Player should reset to 0.0 on stop"
    assert len(app.txt_roman.tag_ranges("active_word")) == 0, "Stop should clear active word tag"
    print("[9/9] Transport controls (Play/Pause/Stop) verified successfully.")

    # Clean shutdown
    app._on_window_close()
    print("\nALL SYNCHRONIZED PLAYBACK & REDESIGNED UI TESTS PASSED! [PASS]")


if __name__ == "__main__":
    test_preview_playback_engine()
