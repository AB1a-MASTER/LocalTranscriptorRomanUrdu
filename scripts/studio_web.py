#!/usr/bin/env python3
"""
Local Speech Studio 2.0 — Web Desktop Server
============================================
Provides a modern, high-performance web-grade backend for Local Speech Studio.
Connects the HTML5/Tailwind 3-column UI to the optimized speech-to-text pipeline
with Server-Sent Events (SSE) for real-time live streaming progress and segments.

Zero external web framework dependencies (uses Python standard library http.server).
Optional native window mode via pywebview.
"""

import os
import sys
import json
import time
import shutil
import urllib.parse
import threading
import mimetypes
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any, List

# Ensure scripts dir is on sys.path
_SCRIPTS_DIR = Path(__file__).resolve().parent
_APP_ROOT = _SCRIPTS_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import transcribe_pipeline as tp
import cleanup
import roman_urdu

# Global state for transcription jobs
CURRENT_JOB = {
    "active": False,
    "cancelled": False,
    "input_path": None,
    "wav_path": None,
    "duration": 0.0,
    "progress_pct": 0.0,
    "speed_factor": 1.0,
    "eta_seconds": 0.0,
    "current_time": 0.0,
    "segments": [],
    "urdu_text": "",
    "roman_text": "",
    "status": "Ready",
    "error": None,
}

EVENT_LISTENERS = []
EVENT_LOCK = threading.Lock()
_CACHED_MODEL = None
_CACHED_MODEL_KEY = None


def broadcast_event(event_type: str, data: Dict[str, Any]):
    """Broadcasts an SSE event to all connected web clients."""
    payload = json.dumps({"type": event_type, "data": data, "timestamp": time.time()})
    msg = f"event: {event_type}\ndata: {payload}\n\n".encode("utf-8")
    with EVENT_LOCK:
        dead_listeners = []
        for wfile in EVENT_LISTENERS:
            try:
                wfile.write(msg)
                wfile.flush()
            except Exception:
                dead_listeners.append(wfile)
        for dead in dead_listeners:
            if dead in EVENT_LISTENERS:
                EVENT_LISTENERS.remove(dead)


def _get_audio_duration(wav_path: Path) -> float:
    """Accurately gets duration in seconds using wave module or ffprobe."""
    try:
        import wave
        with wave.open(str(wav_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return float(frames) / float(rate)
    except Exception:
        pass
    try:
        import subprocess
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(wav_path)]
        ff_out = json.loads(subprocess.check_output(cmd))
        return float(ff_out["format"]["duration"])
    except Exception:
        return 0.0


class StudioRequestHandler(BaseHTTPRequestHandler):
    server_version = "LocalSpeechStudio/2.0"

    def log_message(self, format, *args):
        # Suppress routine GET logging for cleaner terminal output
        if self.path.startswith("/api/events") or self.path.startswith("/media/"):
            return
        super().log_message(format, *args)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 1. API: Server-Sent Events (SSE) Stream
        if path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with EVENT_LOCK:
                EVENT_LISTENERS.append(self.wfile)
            # Keep connection open
            try:
                # Send initial state
                initial_data = {
                    "active": CURRENT_JOB["active"],
                    "status": CURRENT_JOB["status"],
                    "progress_pct": CURRENT_JOB["progress_pct"],
                    "duration": CURRENT_JOB["duration"],
                }
                msg = f"event: init\ndata: {json.dumps(initial_data)}\n\n".encode("utf-8")
                self.wfile.write(msg)
                self.wfile.flush()
                while True:
                    time.sleep(1.0)
                    # heartbeat
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
            except Exception:
                with EVENT_LOCK:
                    if self.wfile in EVENT_LISTENERS:
                        EVENT_LISTENERS.remove(self.wfile)
            return

        # 2. API: System Status
        if path == "/api/status":
            cuda_stat = tp.get_cuda_status()
            models_dir = _APP_ROOT / "models"
            has_large_v3 = False
            has_turbo = False
            if models_dir.is_dir():
                has_large_v3 = any("large-v3" in p.name.lower() and "turbo" not in p.name.lower() for p in models_dir.glob("*"))
                has_turbo = any("turbo" in p.name.lower() for p in models_dir.glob("*"))
            
            resp = {
                "cuda_available": cuda_stat["cuda_available"],
                "device_name": cuda_stat["device_name"],
                "resolved_device": cuda_stat["resolved_device"],
                "compute_type": cuda_stat["compute_type"],
                "compute_types_cuda": cuda_stat["compute_types_cuda"],
                "cpu_threads": tp.CPU_THREADS,
                "cached_large_v3": has_large_v3,
                "cached_turbo": has_turbo,
                "job": CURRENT_JOB,
            }
            self._send_json(resp)
            return

        # 3. API: History
        if path == "/api/history":
            out_dir = _APP_ROOT / "output"
            items = []
            if out_dir.is_dir():
                for f in sorted(out_dir.glob("*.srt"), key=lambda x: x.stat().st_mtime, reverse=True)[:15]:
                    items.append({
                        "filename": f.stem,
                        "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime)),
                        "size_kb": round(f.stat().st_size / 1024, 1),
                    })
            self._send_json(items)
            return

        # 3b. API: Load Historical Transcript
        if path == "/api/load-history":
            query = urllib.parse.parse_qs(parsed.query)
            filename = query.get("name", [""])[0]
            stem = filename.replace("_roman", "").replace(".srt", "").replace(".txt", "")
            out_dir = _APP_ROOT / "output"
            in_dir = _APP_ROOT / "input"

            srt_file = out_dir / f"{stem}.srt"
            roman_srt_file = out_dir / f"{stem}_roman.srt"

            if not srt_file.exists():
                self._send_json({"success": False, "error": f"Transcript {stem}.srt not found"}, status_code=404)
                return

            def parse_time(ts_str):
                ts_str = ts_str.strip().replace(",", ".")
                parts = ts_str.split(":")
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])

            def parse_srt(content):
                blocks = content.strip().split("\n\n")
                entries = []
                for b in blocks:
                    lines = b.strip().splitlines()
                    if len(lines) >= 3 and "-->" in lines[1]:
                        t_parts = lines[1].split("-->")
                        s = parse_time(t_parts[0])
                        e = parse_time(t_parts[1])
                        txt = " ".join(lines[2:]).strip()
                        entries.append({"start": s, "end": e, "text": txt})
                return entries

            urdu_entries = parse_srt(srt_file.read_text(encoding="utf-8", errors="replace"))
            roman_entries = parse_srt(roman_srt_file.read_text(encoding="utf-8", errors="replace")) if roman_srt_file.exists() else []

            loaded_segs = []
            for i, ue in enumerate(urdu_entries):
                re_txt = roman_entries[i]["text"] if i < len(roman_entries) else roman_urdu.transliterate(ue["text"])
                u_toks = ue["text"].split()
                r_toks = re_txt.split()
                n_w = max(len(u_toks), len(r_toks), 1)
                dur = max(0.1, ue["end"] - ue["start"])
                step = dur / n_w
                w_list = []
                for w_idx in range(n_w):
                    wu = u_toks[w_idx] if w_idx < len(u_toks) else ""
                    wr = r_toks[w_idx] if w_idx < len(r_toks) else roman_urdu.transliterate_word(wu)
                    w_list.append({
                        "start": round(ue["start"] + w_idx * step, 3),
                        "end": round(ue["start"] + (w_idx + 1) * step, 3),
                        "urdu": wu,
                        "roman": wr,
                    })
                loaded_segs.append({
                    "start": ue["start"],
                    "end": ue["end"],
                    "start_str": tp.srt_time(ue["start"]).split(",")[0],
                    "end_str": tp.srt_time(ue["end"]).split(",")[0],
                    "urdu": ue["text"],
                    "roman": re_txt,
                    "words": w_list,
                })

            wav_name = None
            for cand in [f"{stem}_audio.wav", f"{stem}.wav", f"{stem}.mp4", f"{stem}.mkv"]:
                if (in_dir / cand).exists():
                    wav_name = cand
                    break

            self._send_json({
                "success": True,
                "filename": f"{stem}.srt",
                "wav_name": wav_name,
                "duration": loaded_segs[-1]["end"] if loaded_segs else 0.0,
                "duration_formatted": loaded_segs[-1]["end_str"] if loaded_segs else "00:00:00",
                "segments": loaded_segs,
            })
            return

        # 4. Media playback & export file streamer
        if path.startswith("/media/"):
            filename = urllib.parse.unquote(path[7:])
            media_path = _APP_ROOT / "input" / filename
            if not media_path.exists():
                media_path = _APP_ROOT / "output" / filename
            if media_path.exists() and media_path.is_file():
                if media_path.suffix.lower() in [".wav", ".mp3", ".m4a", ".mp4", ".mkv", ".webm", ".mov", ".flac", ".ogg"]:
                    self._send_file_stream(media_path)
                else:
                    self._serve_static_file(media_path)
            else:
                self.send_error(404, "File Not Found")
            return

        # 5. Serve static web files from ui_web/
        req_path = path.lstrip("/")
        if not req_path:
            req_path = "index.html"
        file_path = _APP_ROOT / "ui_web" / req_path
        if file_path.is_file():
            self._serve_static_file(file_path)
        else:
            # Fallback to index.html for SPA
            self._serve_static_file(_APP_ROOT / "ui_web" / "index.html")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/cancel":
            CURRENT_JOB["cancelled"] = True
            CURRENT_JOB["status"] = "Cancelled"
            CURRENT_JOB["active"] = False
            broadcast_event("status", {"message": "Transcription cancelled by user."})
            self._send_json({"success": True})
            return

        # Chunked file upload (for browser file picker & drag-and-drop, streams 10GB+ directly to disk)
        if path == "/api/upload":
            try:
                filename = self.headers.get("X-Filename", "audio_input.wav")
                filename = urllib.parse.unquote(filename)
                target_dir = _APP_ROOT / "input"
                target_dir.mkdir(parents=True, exist_ok=True)
                save_path = target_dir / filename

                content_length = int(self.headers.get("Content-Length", 0))
                remaining = content_length
                chunk_size = 64 * 1024

                # Stream upload directly to disk in 64KB chunks
                with open(save_path, "wb") as f:
                    while remaining > 0:
                        to_read = min(chunk_size, remaining)
                        chunk = self.rfile.read(to_read)
                        if not chunk:
                            break
                        f.write(chunk)
                        remaining -= len(chunk)

                # Extract audio to 16kHz mono WAV for Whisper & Web playback
                wav_path = target_dir / f"{save_path.stem}_audio.wav"
                tp.extract_audio(save_path, wav_path)
                duration = _get_audio_duration(wav_path)

                self._send_json({
                    "success": True,
                    "filename": filename,
                    "wav_name": wav_path.name,
                    "duration": duration,
                    "duration_formatted": tp.srt_time(duration).split(",")[0],
                })
            except Exception as exc:
                self._send_json({"success": False, "error": str(exc)}, status_code=500)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        if path == "/api/transcribe":
            try:
                req = json.loads(post_data.decode("utf-8"))
                filename = req.get("filename")
                model_name = req.get("model", "large-v3-turbo")
                device_mode = req.get("device", "auto")
                compute_type = req.get("compute_type", None)
                language = req.get("language", "ur")
                vad_filter = req.get("vad", True)
                beam_size = int(req.get("beam_size", 1))

                input_path = _APP_ROOT / "input" / filename
                if not input_path.exists():
                    self._send_json({"success": False, "error": f"File '{filename}' not found on server"}, status_code=404)
                    return

                # Launch transcription worker in background thread
                t = threading.Thread(
                    target=_transcribe_worker,
                    args=(input_path, model_name, device_mode, compute_type, language, vad_filter, beam_size),
                    daemon=True
                )
                t.start()
                self._send_json({"success": True, "message": "Transcription initiated"})
            except Exception as exc:
                self._send_json({"success": False, "error": str(exc)}, status_code=500)
            return

        if path == "/api/save-transcript":
            try:
                req = json.loads(post_data.decode("utf-8"))
                filename = req.get("filename", "transcript.srt")
                stem = Path(filename).stem.replace("_roman", "")
                segments = req.get("segments", [])

                out_dir = _APP_ROOT / "output"
                out_dir.mkdir(parents=True, exist_ok=True)

                updated_segments = []
                urdu_lines = []
                roman_lines = []
                srt_entries = []
                roman_srt_entries = []
                vtt_entries = ["WEBVTT\n"]
                csv_rows = ["Index,Start Seconds,End Seconds,Start Time,End Time,Urdu Text,Roman Urdu / English Text"]

                for i, s in enumerate(segments):
                    s_start = float(s.get("start", 0.0))
                    s_end = float(s.get("end", 0.0))
                    s_urdu = s.get("urdu", "").strip()
                    s_roman = s.get("roman", "").strip()
                    if not s_roman:
                        s_roman = roman_urdu.transliterate(s_urdu)

                    start_str = tp.srt_time(s_start).split(",")[0]
                    end_str = tp.srt_time(s_end).split(",")[0]
                    srt_s = tp.srt_time(s_start)
                    srt_e = tp.srt_time(s_end)
                    vtt_s = srt_s.replace(",", ".")
                    vtt_e = srt_e.replace(",", ".")

                    urdu_lines.append(s_urdu)
                    roman_lines.append(s_roman)

                    idx = i + 1
                    srt_entries.append(f"{idx}\n{srt_s} --> {srt_e}\n{s_urdu}\n")
                    roman_srt_entries.append(f"{idx}\n{srt_s} --> {srt_e}\n{s_roman}\n")
                    vtt_entries.append(f"{idx}\n{vtt_s} --> {vtt_e}\n{s_roman}\n")

                    safe_u = '"' + s_urdu.replace('"', '""') + '"'
                    safe_r = '"' + s_roman.replace('"', '""') + '"'
                    csv_rows.append(f"{idx},{s_start:.3f},{s_end:.3f},{start_str},{end_str},{safe_u},{safe_r}")

                    w_tokens = s.get("words", [])
                    u_toks = s_urdu.split()
                    r_toks = s_roman.split()

                    if not w_tokens or len(w_tokens) != max(len(u_toks), len(r_toks)):
                        num_w = max(len(u_toks), len(r_toks), 1)
                        dur = max(0.1, s_end - s_start)
                        step = dur / num_w
                        w_tokens = []
                        for w_idx in range(num_w):
                            wu = u_toks[w_idx] if w_idx < len(u_toks) else ""
                            wr = r_toks[w_idx] if w_idx < len(r_toks) else roman_urdu.transliterate_word(wu)
                            w_tokens.append({
                                "start": round(s_start + w_idx * step, 3),
                                "end": round(s_start + (w_idx + 1) * step, 3),
                                "urdu": wu,
                                "roman": wr,
                            })

                    updated_segments.append({
                        "start": s_start,
                        "end": s_end,
                        "start_str": start_str,
                        "end_str": end_str,
                        "urdu": s_urdu,
                        "roman": s_roman,
                        "words": w_tokens,
                    })

                # Write all output files
                txt_path = out_dir / f"{stem}.txt"
                txt_path.write_text("\n".join(urdu_lines) + "\n", encoding="utf-8")

                roman_txt_path = out_dir / f"{stem}_roman.txt"
                roman_txt_path.write_text("\n".join(roman_lines) + "\n", encoding="utf-8")

                srt_path = out_dir / f"{stem}.srt"
                srt_path.write_text("\n".join(srt_entries) + "\n", encoding="utf-8")

                roman_srt_path = out_dir / f"{stem}_roman.srt"
                roman_srt_path.write_text("\n".join(roman_srt_entries) + "\n", encoding="utf-8")

                vtt_path = out_dir / f"{stem}.vtt"
                vtt_path.write_text("\n".join(vtt_entries) + "\n", encoding="utf-8")

                csv_path = out_dir / f"{stem}.csv"
                csv_path.write_text("\n".join(csv_rows) + "\n", encoding="utf-8")

                json_path = out_dir / f"{stem}.json"
                json_payload = {
                    "filename": stem,
                    "total_segments": len(updated_segments),
                    "duration": updated_segments[-1]["end"] if updated_segments else 0.0,
                    "segments": updated_segments,
                }
                json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

                CURRENT_JOB["segments"] = updated_segments
                CURRENT_JOB["urdu_text"] = " ".join(urdu_lines)
                CURRENT_JOB["roman_text"] = " ".join(roman_lines)

                self._send_json({
                    "success": True,
                    "message": "Transcript saved and all export formats updated.",
                    "segments": updated_segments,
                    "files": {
                        "urdu_srt": srt_path.name,
                        "roman_srt": roman_srt_path.name,
                        "urdu_txt": txt_path.name,
                        "roman_txt": roman_txt_path.name,
                        "vtt": vtt_path.name,
                        "csv": csv_path.name,
                        "json": json_path.name,
                    }
                })
            except Exception as exc:
                self._send_json({"success": False, "error": str(exc)}, status_code=500)
            return

        self.send_error(404, "Unknown API Route")

    def _send_json(self, data: Any, status_code: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static_file(self, file_path: Path):
        mime, _ = mimetypes.guess_type(str(file_path))
        if mime is None:
            if file_path.suffix == ".html":
                mime = "text/html; charset=utf-8"
            elif file_path.suffix in [".srt", ".vtt", ".txt"]:
                mime = "text/plain; charset=utf-8"
            elif file_path.suffix == ".csv":
                mime = "text/csv; charset=utf-8"
            elif file_path.suffix == ".json":
                mime = "application/json; charset=utf-8"
            else:
                mime = "application/octet-stream"
        else:
            if mime.startswith("text/"):
                mime += "; charset=utf-8"
        try:
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        except Exception as exc:
            self.send_error(500, f"Error reading file: {exc}")

    def _send_file_stream(self, file_path: Path):
        """Sends audio file supporting byte-range requests for smooth seeking in HTML5 audio player."""
        file_size = file_path.stat().st_size
        range_header = self.headers.get("Range")

        if range_header:
            # Parse Range: bytes=START-END
            try:
                ranges = range_header.replace("bytes=", "").split("-")
                start = int(ranges[0]) if ranges[0] else 0
                end = int(ranges[1]) if len(ranges) > 1 and ranges[1] else file_size - 1
            except ValueError:
                start = 0
                end = file_size - 1

            length = (end - start) + 1
            self.send_response(206)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(length))
            self.end_headers()

            with open(file_path, "rb") as f:
                f.seek(start)
                bytes_to_send = length
                buf_size = 64 * 1024
                while bytes_to_send > 0:
                    read_len = min(buf_size, bytes_to_send)
                    data = f.read(read_len)
                    if not data:
                        break
                    self.wfile.write(data)
                    bytes_to_send -= len(data)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(file_size))
            self.end_headers()
            with open(file_path, "rb") as f:
                shutil.copyfileobj(f, self.wfile)


def _transcribe_worker(input_path: Path, model_name: str, device_mode: str, compute_type: Optional[str], language: str, vad_filter: bool, beam_size: int):
    global _CACHED_MODEL, _CACHED_MODEL_KEY

    CURRENT_JOB["active"] = True
    CURRENT_JOB["cancelled"] = False
    CURRENT_JOB["input_path"] = str(input_path)
    CURRENT_JOB["segments"] = []
    CURRENT_JOB["progress_pct"] = 0.0
    CURRENT_JOB["status"] = "Preparing audio..."
    CURRENT_JOB["error"] = None

    broadcast_event("status", {"message": "Preparing audio stream..."})

    try:
        if input_path.suffix.lower() == ".wav":
            wav_path = input_path
        else:
            wav_path = _APP_ROOT / "input" / f"{input_path.stem}_audio.wav"
            if not wav_path.exists():
                broadcast_event("status", {"message": "Extracting 16kHz audio with FFmpeg..."})
                tp.extract_audio(input_path, wav_path)

        CURRENT_JOB["wav_path"] = str(wav_path)

        # Resolve device
        resolved_device, resolved_compute, _ = tp.resolve_device(device_mode, compute_type)
        model_key = f"{model_name}_{resolved_device}_{resolved_compute}"

        if _CACHED_MODEL is None or _CACHED_MODEL_KEY != model_key:
            dev_label = "CUDA GPU" if resolved_device == "cuda" else f"CPU ({tp.CPU_THREADS} threads)"
            status_msg = f"Loading {model_name} on {dev_label} ({resolved_compute})..."
            CURRENT_JOB["status"] = status_msg
            broadcast_event("status", {"message": status_msg})
            _CACHED_MODEL = tp.load_model(model_name, device=device_mode, compute_type=resolved_compute)
            _CACHED_MODEL_KEY = model_key

        model = _CACHED_MODEL
        CURRENT_JOB["status"] = "Transcribing speech..."
        broadcast_event("status", {"message": "Transcribing speech with Faster-Whisper..."})

        def progress_cb(prog):
            if CURRENT_JOB["cancelled"]:
                raise RuntimeError("Transcription cancelled by user.")

            CURRENT_JOB["progress_pct"] = round(prog["progress_pct"], 1)
            CURRENT_JOB["speed_factor"] = round(prog["speed_factor"], 1)
            CURRENT_JOB["eta_seconds"] = round(prog["eta_seconds"], 1)
            CURRENT_JOB["current_time"] = round(prog["current_time"], 1)
            CURRENT_JOB["duration"] = round(prog["total_duration"], 1)

            # Transliterate segment for live streaming view
            seg = prog["segment"]
            clean_urdu_seg = cleanup.clean_urdu_text(seg.text)
            clean_roman_seg = cleanup.clean_roman_text(roman_urdu.transliterate(clean_urdu_seg))

            # Build word-level timestamp objects
            words_data = []
            seg_words = getattr(seg, 'words', None) or []
            if seg_words:
                for w in seg_words:
                    raw_w = w.word.strip()
                    if not raw_w:
                        continue
                    r_w = roman_urdu.transliterate_word(raw_w)
                    words_data.append({
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                        "urdu": raw_w,
                        "roman": r_w,
                    })
            else:
                u_tokens = [w for w in clean_urdu_seg.split() if w]
                r_tokens = [w for w in clean_roman_seg.split() if w]
                num_w = max(len(u_tokens), len(r_tokens), 1)
                seg_dur = max(0.1, seg.end - seg.start)
                w_step = seg_dur / num_w
                for i in range(num_w):
                    u_w = u_tokens[i] if i < len(u_tokens) else ""
                    r_w = r_tokens[i] if i < len(r_tokens) else roman_urdu.transliterate_word(u_w)
                    words_data.append({
                        "start": round(seg.start + i * w_step, 3),
                        "end": round(seg.start + (i + 1) * w_step, 3),
                        "urdu": u_w,
                        "roman": r_w,
                    })

            seg_payload = {
                "start": seg.start,
                "end": seg.end,
                "start_str": tp.srt_time(seg.start).split(",")[0],
                "end_str": tp.srt_time(seg.end).split(",")[0],
                "urdu": clean_urdu_seg,
                "roman": clean_roman_seg,
                "words": words_data,
            }
            CURRENT_JOB["segments"].append(seg_payload)

            broadcast_event("progress", {
                "progress_pct": CURRENT_JOB["progress_pct"],
                "speed_factor": CURRENT_JOB["speed_factor"],
                "eta_seconds": CURRENT_JOB["eta_seconds"],
                "current_time": CURRENT_JOB["current_time"],
                "total_duration": CURRENT_JOB["duration"],
                "latest_segment": seg_payload,
            })

        # Run transcription with streaming callbacks
        raw_segs, info = tp.run_transcription(
            model=model,
            wav=wav_path,
            language=language,
            beam_size=beam_size,
            vad_filter=vad_filter,
            word_timestamps=True,
            progress_callback=progress_cb
        )

        if CURRENT_JOB["cancelled"]:
            return

        broadcast_event("status", {"message": "Post-processing subtitles and Roman transliteration..."})

        # Final cleanup and full text formation
        cleaned_segs = cleanup.clean_segments(raw_segs)
        raw_urdu = " ".join(s.text.strip() for s in cleaned_segs)
        clean_urdu = cleanup.clean_urdu_text(raw_urdu)
        clean_roman = cleanup.clean_roman_text(roman_urdu.transliterate(clean_urdu))

        # Save standard outputs
        out_dir = _APP_ROOT / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = input_path.stem
        if stem.endswith("_audio"):
            stem = stem[:-6]

        txt_path = out_dir / f"{stem}.txt"
        txt_path.write_text(clean_urdu + "\n", encoding="utf-8")

        srt_path = out_dir / f"{stem}.srt"
        tp.write_srt(cleaned_segs, srt_path)

        roman_txt_path = out_dir / f"{stem}_roman.txt"
        roman_txt_path.write_text(clean_roman + "\n", encoding="utf-8")

        raw_roman_srt = roman_urdu.transliterate_srt(srt_path.read_text(encoding="utf-8"))
        clean_roman_srt = cleanup.clean_roman_text_in_srt(raw_roman_srt)
        roman_srt_path = out_dir / f"{stem}_roman.srt"
        roman_srt_path.write_text(clean_roman_srt, encoding="utf-8")

        # Final segment formatting with word timestamps for accurate playback synchronization
        final_segments = []
        for s in cleaned_segs:
            u_text = cleanup.clean_urdu_text(s.text.strip())
            r_text = cleanup.clean_roman_text(roman_urdu.transliterate(u_text))
            w_objs = getattr(s, 'words', None) or []
            w_list = []
            if w_objs:
                for w in w_objs:
                    w_u = w.word.strip()
                    if not w_u:
                        continue
                    w_r = roman_urdu.transliterate_word(w_u)
                    w_list.append({
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                        "urdu": w_u,
                        "roman": w_r,
                    })
            else:
                u_toks = [w for w in u_text.split() if w]
                r_toks = [w for w in r_text.split() if w]
                n_w = max(len(u_toks), len(r_toks), 1)
                dur = max(0.1, s.end - s.start)
                step = dur / n_w
                for i in range(n_w):
                    wu = u_toks[i] if i < len(u_toks) else ""
                    wr = r_toks[i] if i < len(r_toks) else roman_urdu.transliterate_word(wu)
                    w_list.append({
                        "start": round(s.start + i * step, 3),
                        "end": round(s.start + (i + 1) * step, 3),
                        "urdu": wu,
                        "roman": wr,
                    })

            final_segments.append({
                "start": s.start,
                "end": s.end,
                "start_str": tp.srt_time(s.start).split(",")[0],
                "end_str": tp.srt_time(s.end).split(",")[0],
                "urdu": u_text,
                "roman": r_text,
                "words": w_list,
            })

        # Generate WebVTT, CSV, and JSON formats
        vtt_entries = ["WEBVTT\n"]
        csv_rows = ["Index,Start Seconds,End Seconds,Start Time,End Time,Urdu Text,Roman Urdu / English Text"]
        for idx, s in enumerate(final_segments, 1):
            vs = tp.srt_time(s["start"]).replace(",", ".")
            ve = tp.srt_time(s["end"]).replace(",", ".")
            vtt_entries.append(f"{idx}\n{vs} --> {ve}\n{s['roman']}\n")
            su = '"' + s["urdu"].replace('"', '""') + '"'
            sr = '"' + s["roman"].replace('"', '""') + '"'
            csv_rows.append(f"{idx},{s['start']:.3f},{s['end']:.3f},{s['start_str']},{s['end_str']},{su},{sr}")

        vtt_path = out_dir / f"{stem}.vtt"
        vtt_path.write_text("\n".join(vtt_entries) + "\n", encoding="utf-8")

        csv_path = out_dir / f"{stem}.csv"
        csv_path.write_text("\n".join(csv_rows) + "\n", encoding="utf-8")

        json_path = out_dir / f"{stem}.json"
        json_payload = {
            "filename": stem,
            "total_segments": len(final_segments),
            "duration": final_segments[-1]["end"] if final_segments else 0.0,
            "segments": final_segments,
        }
        json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        CURRENT_JOB["segments"] = final_segments
        CURRENT_JOB["active"] = False
        CURRENT_JOB["status"] = "Completed"
        CURRENT_JOB["urdu_text"] = clean_urdu
        CURRENT_JOB["roman_text"] = clean_roman
        CURRENT_JOB["progress_pct"] = 100.0

        broadcast_event("completed", {
            "urdu_text": clean_urdu,
            "roman_text": clean_roman,
            "segments_count": len(cleaned_segs),
            "segments": final_segments,
            "files": {
                "urdu_txt": str(txt_path.name),
                "urdu_srt": str(srt_path.name),
                "roman_txt": str(roman_txt_path.name),
                "roman_srt": str(roman_srt_path.name),
                "vtt": str(vtt_path.name),
                "csv": str(csv_path.name),
                "json": str(json_path.name),
            }
        })

    except Exception as exc:
        if not CURRENT_JOB["cancelled"]:
            CURRENT_JOB["active"] = False
            CURRENT_JOB["status"] = "Error"
            CURRENT_JOB["error"] = str(exc)
            broadcast_event("error", {"error": str(exc)})


def start_server(port: int = 7860, open_browser: bool = True):
    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, StudioRequestHandler)
    print("=" * 65)
    print("  LOCAL SPEECH STUDIO 2.0 — MODERN DESKTOP SERVER ACTIVE")
    print(f"  URL: http://127.0.0.1:{port}")
    print("=" * 65)

    if open_browser:
        import webbrowser
        threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Local Speech Studio 2.0 Server")
    parser.add_argument("--port", type=int, default=7860, help="Port to serve UI (default 7860)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    start_server(port=args.port, open_browser=not args.no_browser)

