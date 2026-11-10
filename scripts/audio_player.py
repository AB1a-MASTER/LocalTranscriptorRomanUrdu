"""
Local Audio Player Engine for Urdu-English Transcriber UI.
Provides sub-millisecond seeking, non-blocking playback, PyAV multi-format decoding,
and thread-safe position tracking for synchronized word highlighting.
"""

import sys
import threading
import time
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

# Optional imports with graceful fallbacks
try:
    import av
    HAS_AV = True
except ImportError:
    HAS_AV = False

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except (ImportError, OSError):
    HAS_SOUNDDEVICE = False


class AudioPlayer:
    """
    High-precision local audio player supporting MP3, WAV, MP4, MKV, M4A, etc.
    Decodes audio to 44.1kHz 32-bit float PCM array and streams via sounddevice.
    """

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.audio_data: Optional[np.ndarray] = None
        self.duration: float = 0.0
        self.current_frame: int = 0
        self.is_playing: bool = False
        self.volume: float = 1.0
        self.filepath: Optional[Path] = None

        self._lock = threading.RLock()
        self._stream: Optional[sd.OutputStream] = None
        self._device_available = HAS_SOUNDDEVICE

        if HAS_SOUNDDEVICE:
            try:
                # Query default output device to verify availability
                sd.query_devices(kind="output")
            except Exception as exc:
                print(f"[AudioPlayer] Output audio device unavailable: {exc}")
                self._device_available = False

    def load(self, filepath: str | Path) -> bool:
        """
        Loads and decodes audio from an audio or video file into memory.
        Returns True on success, False on failure.
        """
        path = Path(filepath)
        if not path.exists():
            return False

        with self._lock:
            self.stop()
            self.audio_data = None
            self.duration = 0.0
            self.current_frame = 0
            self.filepath = path

        try:
            data = None

            # 1. Primary decoder: PyAV (decodes any container: MP4, MKV, MP3, WAV, etc.)
            if HAS_AV:
                try:
                    container = av.open(str(path))
                    if container.streams.audio:
                        stream = container.streams.audio[0]
                        resampler = av.AudioResampler(format="fltp", layout="mono", rate=self.sample_rate)
                        chunks = []

                        for frame in container.decode(stream):
                            for r_frame in resampler.resample(frame):
                                chunks.append(r_frame.to_ndarray())

                        container.close()

                        if chunks:
                            arr = np.concatenate(chunks, axis=1)[0]
                            data = arr.astype(np.float32)
                except Exception as av_err:
                    print(f"[AudioPlayer] PyAV decode note: {av_err}. Falling back to FFmpeg...")

            # 2. Secondary fallback: FFmpeg (supports 100% of camera/broadcast footage codecs)
            if data is None:
                import tempfile
                import subprocess
                try:
                    import cuda_helper
                    ffmpeg_bin = cuda_helper.get_ffmpeg_binary()
                except Exception:
                    ffmpeg_bin = "ffmpeg"

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                    tmp_wav = tf.name

                try:
                    cmd = [
                        ffmpeg_bin, "-y",
                        "-vn",
                        "-i", str(path),
                        "-ar", str(self.sample_rate),
                        "-ac", "1",
                        "-c:a", "pcm_f32le",
                        tmp_wav
                    ]
                    res = subprocess.run(cmd, capture_output=True, text=False)
                    if res.returncode == 0 and Path(tmp_wav).exists():
                        with open(tmp_wav, "rb") as wf:
                            wf.seek(44)  # Skip standard 44-byte WAV header
                            data = np.fromfile(wf, dtype=np.float32)
                except Exception as ff_err:
                    print(f"[AudioPlayer] FFmpeg fallback error: {ff_err}")
                finally:
                    if Path(tmp_wav).exists():
                        try:
                            Path(tmp_wav).unlink()
                        except Exception:
                            pass

            # 3. Last fallback: Python wave module for standard uncompressed WAV
            if data is None and path.suffix.lower() == ".wav":
                import wave
                with wave.open(str(path), "rb") as wf:
                    n_channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    orig_sr = wf.getframerate()
                    frames = wf.readframes(wf.getnframes())

                if sampwidth == 2:
                    raw = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                elif sampwidth == 1:
                    raw = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
                else:
                    raw = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0

                if n_channels > 1:
                    raw = raw.reshape(-1, n_channels).mean(axis=1)

                if orig_sr != self.sample_rate:
                    orig_len = len(raw)
                    new_len = int(orig_len * self.sample_rate / orig_sr)
                    data = np.interp(np.linspace(0, orig_len, new_len, endpoint=False), np.arange(orig_len), raw).astype(np.float32)
                else:
                    data = raw

            if data is None or len(data) == 0:
                print(f"[AudioPlayer] Failed to extract audio stream from '{path.name}'.")
                return False

            with self._lock:
                self.audio_data = data
                self.duration = len(data) / self.sample_rate
                self.current_frame = 0

            return True

        except Exception as exc:
            print(f"[AudioPlayer] Error decoding '{path.name}': {exc}")
            return False

    def _ensure_stream(self) -> bool:
        """Ensures the background sounddevice output stream is open and running."""
        if not self._device_available or not HAS_SOUNDDEVICE:
            return False

        if self._stream is None or not self._stream.active:
            try:
                self._stream = sd.OutputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="float32",
                    callback=self._audio_callback
                )
                self._stream.start()
                return True
            except Exception as exc:
                print(f"[AudioPlayer] Failed to initialize audio stream: {exc}")
                self._device_available = False
                return False
        return True

    def _audio_callback(self, outdata: np.ndarray, frames: int, time_info, status):
        """Low-latency audio callback invoked by PortAudio."""
        with self._lock:
            if not self.is_playing or self.audio_data is None:
                outdata.fill(0)
                return

            total_frames = len(self.audio_data)
            remaining = total_frames - self.current_frame

            if remaining <= 0:
                outdata.fill(0)
                self.is_playing = False
                return

            chunk_len = min(frames, remaining)
            # Copy mono frames
            chunk = self.audio_data[self.current_frame : self.current_frame + chunk_len]
            if self.volume != 1.0:
                chunk = np.clip(chunk * self.volume, -1.0, 1.0)

            outdata[:chunk_len, 0] = chunk
            if chunk_len < frames:
                outdata[chunk_len:, 0] = 0.0
                self.is_playing = False

            self.current_frame += chunk_len

    def play(self) -> bool:
        """Starts or resumes audio playback."""
        with self._lock:
            if self.audio_data is None:
                return False

            if self.current_frame >= len(self.audio_data):
                self.current_frame = 0

            self.is_playing = True

        return self._ensure_stream()

    def pause(self):
        """Pauses audio playback, retaining current position."""
        with self._lock:
            self.is_playing = False

    def toggle_play(self) -> bool:
        """Toggles between play and pause."""
        if self.is_playing:
            self.pause()
            return False
        else:
            return self.play()

    def stop(self):
        """Stops playback and resets position to beginning."""
        with self._lock:
            self.is_playing = False
            self.current_frame = 0

    def seek(self, seconds: float):
        """Seeks to position in seconds."""
        with self._lock:
            if self.audio_data is None:
                return
            target = int(seconds * self.sample_rate)
            self.current_frame = max(0, min(target, len(self.audio_data)))

    def get_position(self) -> float:
        """Returns current playback position in seconds."""
        with self._lock:
            if self.audio_data is None:
                return 0.0
            return self.current_frame / self.sample_rate

    def get_duration(self) -> float:
        """Returns total duration of loaded audio in seconds."""
        with self._lock:
            return self.duration

    def is_loaded(self) -> bool:
        """Returns True if audio data is loaded and ready."""
        with self._lock:
            return self.audio_data is not None

    def set_volume(self, volume: float):
        """Sets playback volume between 0.0 (silent) and 1.5 (boosted)."""
        with self._lock:
            self.volume = max(0.0, min(float(volume), 1.5))

    def close(self):
        """Closes audio output stream and releases resources."""
        with self._lock:
            self.is_playing = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
