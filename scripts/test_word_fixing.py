"""
test_word_fixing.py
===================
Unit tests verifying:
  1. Surgical single-instance word replacement (leaving identical duplicates untouched)
  2. Document-wide word replacement (replace all)
  3. Word-level timestamp synchronization and recalibration via SequenceMatcher
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import difflib
import re


def test_single_word_replacement():
    print("Test 1: Surgical Single-Instance Word Replacement")
    # Simulate a sentence with 3 duplicate words ("test")
    # Where word 2 was wrong, but words 1 and 3 were correct!
    original = "This test audio is a very good test clip for our final test."

    # Indices of the 2nd "test"
    # "This " is 5 chars -> word 1 starts at 5, ends at 9
    # "This test audio is a very good " is 31 chars -> word 2 starts at 31, ends at 35
    s_idx = 31
    e_idx = 35
    target_word = original[s_idx:e_idx]
    assert target_word == "test", f"Expected 'test', got '{target_word}'"

    # Surgical replacement at indices
    replacement = "exam"
    result = original[:s_idx] + replacement + original[e_idx:]
    expected = "This test audio is a very good exam clip for our final test."
    assert result == expected, f"Failed single word replacement:\nGot: '{result}'\nExp: '{expected}'"
    print(f"  [PASS] Only the 2nd 'test' replaced: '{result}'")


def test_replace_all():
    print("\nTest 2: Document-Wide Word Replacement")
    original = "This test audio is a very good test clip for our final test."
    wrong = "test"
    right = "exam"
    pattern = re.compile(r"\b" + re.escape(wrong) + r"\b")
    result = pattern.sub(right, original)
    expected = "This exam audio is a very good exam clip for our final exam."
    assert result == expected, f"Failed replace all: '{result}'"
    print(f"  [PASS] All 3 occurrences replaced: '{result}'")


def test_timing_recalibration():
    print("\nTest 3: Word-Level Subtitle Timing Recalibration")
    # 5 words with exact timestamps
    base_timed = [
        {"word": "This", "start": 0.0, "end": 0.5},
        {"word": "sodnts", "start": 0.5, "end": 1.2},    # Misrecognized word
        {"word": "is", "start": 1.2, "end": 1.5},
        {"word": "very", "start": 1.5, "end": 1.8},
        {"word": "good", "start": 1.8, "end": 2.3},
    ]

    # User corrected word 2: "sodnts" -> "students"
    edited_text = "This students is very good"
    edited_words = edited_text.split()

    orig_strings = [tw["word"] for tw in base_timed]
    matcher = difflib.SequenceMatcher(None, orig_strings, edited_words)

    recalibrated = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for idx in range(j2 - j1):
                recalibrated.append((edited_words[j1 + idx], base_timed[i1 + idx]["start"], base_timed[i1 + idx]["end"]))
        elif tag == "replace":
            t_start = base_timed[i1]["start"]
            t_end = base_timed[i2 - 1]["end"]
            dur = max(0.01, t_end - t_start)
            count = j2 - j1
            for idx in range(count):
                w_start = t_start + (idx * dur / count)
                w_end = t_start + ((idx + 1) * dur / count)
                recalibrated.append((edited_words[j1 + idx], w_start, w_end))

    # Verify:
    # Word "This" retains 0.0 -> 0.5
    assert recalibrated[0] == ("This", 0.0, 0.5)
    # Word "students" receives exact timestamp of replaced word: 0.5 -> 1.2
    assert recalibrated[1] == ("students", 0.5, 1.2)
    # Word "is" retains 1.2 -> 1.5
    assert recalibrated[2] == ("is", 1.2, 1.5)
    print("  [PASS] Timestamps for unmodified words preserved exactly.")
    print(f"  [PASS] Corrected word 'students' automatically inherited exact timestamp: {recalibrated[1][1]}s -> {recalibrated[1][2]}s")


if __name__ == "__main__":
    test_single_word_replacement()
    test_replace_all()
    test_timing_recalibration()
    print("\nALL WORD FIXING & TIMING RECALIBRATION TESTS PASSED (3/3)!")

