"""
Unit tests for AudioPlayer engine.
"""

import time
from pathlib import Path
from audio_player import AudioPlayer

def test_audio_player():
    player = AudioPlayer()
    
    # Test 1: WAV loading
    wav_path = Path("input/test.wav")
    assert wav_path.exists(), "input/test.wav not found"
    assert player.load(wav_path), "Failed to load WAV"
    assert player.is_loaded(), "Player reports not loaded"
    dur = player.get_duration()
    print(f"Test 1 (WAV): duration = {dur:.2f}s (expected ~19.4s)")
    assert 19.0 <= dur <= 20.0, f"Unexpected duration: {dur}"

    # Test 2: MP3 loading
    mp3_path = Path("input/test2.mp3")
    assert mp3_path.exists(), "input/test2.mp3 not found"
    assert player.load(mp3_path), "Failed to load MP3"
    dur_mp3 = player.get_duration()
    print(f"Test 2 (MP3): duration = {dur_mp3:.2f}s (expected ~57.5s)")
    assert 57.0 <= dur_mp3 <= 58.0, f"Unexpected MP3 duration: {dur_mp3}"

    # Test 3: MP4 video loading
    mp4_path = Path("input/test3english.mp4")
    assert mp4_path.exists(), "input/test3english.mp4 not found"
    assert player.load(mp4_path), "Failed to load MP4"
    dur_mp4 = player.get_duration()
    print(f"Test 3 (MP4): duration = {dur_mp4:.2f}s (expected ~23.8s)")
    assert 23.0 <= dur_mp4 <= 24.5, f"Unexpected MP4 duration: {dur_mp4}"

    # Test 4: Seeking & Position
    player.seek(10.5)
    pos = player.get_position()
    print(f"Test 4 (Seek): pos = {pos:.2f}s (expected ~10.5s)")
    assert abs(pos - 10.5) < 0.05, f"Seek inaccurate: {pos}"

    # Test 5: Play & Pause
    player.play()
    assert player.is_playing, "Player did not report playing"
    time.sleep(0.3)
    pos_after_play = player.get_position()
    print(f"Test 5 (Play): pos after 0.3s = {pos_after_play:.2f}s")
    assert pos_after_play > 10.5, "Position did not advance during playback"

    player.pause()
    assert not player.is_playing, "Player did not report paused"
    pos_paused = player.get_position()
    time.sleep(0.2)
    assert abs(player.get_position() - pos_paused) < 0.01, "Position advanced while paused"

    # Test 6: Stop
    player.stop()
    assert not player.is_playing, "Player did not stop"
    assert player.get_position() == 0.0, "Position did not reset on stop"

    player.close()
    print("ALL AUDIO PLAYER TESTS PASSED SUCCESSFULLY! [PASS]")

if __name__ == "__main__":
    test_audio_player()
