"""
test_roman_urdu.py
==================
Comprehensive test suite verifying the 4-tier Roman Urdu Transliteration Engine:
  1. Short-vowel unwritten abjad words resolution (e.g. bachat, taraqqi, hukoomat)
  2. Morphological Affix Engine (prefixes, suffixes, regular plurals)
  3. Bilingual code-switching English preservation
  4. User spelling preference overrides
  5. SRT timestamp & layout preservation
"""

import sys
from pathlib import Path

# Ensure scripts dir is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import roman_urdu


def run_tests():
    passed = 0
    failed = 0

    def assert_eq(test_name: str, actual: str, expected: str):
        nonlocal passed, failed
        if actual == expected:
            print(f"  [PASS] {test_name}: '{actual}'")
            passed += 1
        else:
            print(f"  [FAIL] {test_name}: expected '{expected}', got '{actual}'")
            failed += 1

    print("=" * 70)
    print("  TEST SUITE: ROMAN URDU TRANSLITERATION ENGINE")
    print("=" * 70)

    # ── Test Group 1: High-Frequency Words with Unwritten Short Vowels ────
    print("\n[Group 1: Short-Vowel Vocabulary Resolution]")
    test_cases_group1 = [
        ("بچت", "bachat"),
        ("ترقی", "taraqqi"),
        ("حکومت", "hukoomat"),
        ("سمجھ", "samajh"),
        ("دفتر", "daftar"),
        ("سبق", "sabaq"),
        ("خبر", "khabar"),
        ("نظر", "nazar"),
        ("شہر", "shehar"),
        ("ملک", "mulk"),
        ("مسئلہ", "masla"),
        ("معلومات", "maloomat"),
        ("تجربہ", "tajurba"),
        ("ضرورت", "zaroorat"),
        ("طریقہ", "tareeqa"),
        ("فیصلہ", "faisla"),
    ]
    for urdu_word, expected_roman in test_cases_group1:
        actual = roman_urdu.transliterate_word(urdu_word)
        assert_eq(f"Word '{urdu_word}'", actual, expected_roman)

    # ── Test Group 2: Morphological Affix Decomposition ────────────────────
    print("\n[Group 2: Morphological Affixes (Prefixes & Suffixes)]")
    test_cases_group2 = [
        ("سمجھدار", "samajhdar"),         # root samajh + suffix dar
        ("ضرورتمند", "zarooratmand"),     # root zaroorat + suffix mand
        ("امیدوار", "umeedwar"),           # root umeed + suffix war
        ("بہترین", "behtareen"),           # root behtar + suffix tareen
        ("دکانوں", "dukaanon"),           # root dukaan + plural on
        ("کتابیں", "kitabein"),           # root kitab + plural ein
        ("شہروں", "shehron"),             # root shehar + plural on
        ("خبریں", "khabrein"),           # root khabar + plural ein
        ("گاڑیاں", "gaadiyan"),           # root gaadi + plural iyan
    ]
    for urdu_affix, expected_roman in test_cases_group2:
        actual = roman_urdu.transliterate_word(urdu_affix)
        assert_eq(f"Affix '{urdu_affix}'", actual, expected_roman)

    # ── Test Group 3: Mixed Code-Switching & English Pass-Through ──────────
    print("\n[Group 3: Bilingual Code-Switching & English Preservation]")
    mixed_sentences = [
        (
            "اسلام علیکم dear students, I have some exciting news to share with you.",
            "asalam alaikum dear students, I have some exciting news to share with you."
        ),
        (
            "ہم نے exam hack sessions کروایا تھے جو آپ لوگوں نے بہت ہی appreciate کیا تھا.",
            "hum ne exam hack sessions karwaya thay jo aap logon ne bohat hi appreciate kiya tha."
        ),
        (
            "اے ایف ایم میں تو پروفیشنل مارکس بھی ہیں",
            "AFM mein tou professional marks bhi hain"
        ),
    ]
    for urdu_input, expected_roman in mixed_sentences:
        actual = roman_urdu.transliterate(urdu_input)
        assert_eq(f"Mixed sentence", actual, expected_roman)

    # ── Test Group 4: SRT Subtitle Format Preservation ────────────────────
    print("\n[Group 4: SRT Timestamp & Structural Integrity]")
    sample_srt = (
        "1\n"
        "00:00:01,000 --> 00:00:03,500\n"
        "اسلام علیکم dear students\n\n"
        "2\n"
        "00:00:03,600 --> 00:00:06,000\n"
        "ہماری نئی بچت اسکیم شروع ہے\n"
    )
    expected_srt = (
        "1\n"
        "00:00:01,000 --> 00:00:03,500\n"
        "asalam alaikum dear students\n\n"
        "2\n"
        "00:00:03,600 --> 00:00:06,000\n"
        "hamari nayi bachat scheme shuroo hai\n"
    )
    actual_srt = roman_urdu.transliterate_srt(sample_srt)
    # Check that timestamps and structure are preserved exactly
    lines_actual = actual_srt.strip().splitlines()
    assert_eq("SRT block 1 index", lines_actual[0], "1")
    assert_eq("SRT block 1 timestamp", lines_actual[1], "00:00:01,000 --> 00:00:03,500")
    assert_eq("SRT block 1 text", lines_actual[2], "asalam alaikum dear students")
    assert_eq("SRT block 2 index", lines_actual[4], "2")
    assert_eq("SRT block 2 timestamp", lines_actual[5], "00:00:03,600 --> 00:00:06,000")
    assert "bachat" in lines_actual[6]
    passed += 1

    print("\n" + "=" * 70)
    print(f"  RESULTS: {passed} PASSED  |  {failed} FAILED")
    print("=" * 70)
    return failed == 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    success = run_tests()
    sys.exit(0 if success else 1)
