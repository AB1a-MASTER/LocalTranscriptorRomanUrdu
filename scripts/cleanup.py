"""
cleanup.py
==========
Post-transcription cleanup module for local speech-to-text.

Cleans transcripts while strictly adhering to the working principle:
  - Do NOT rewrite or translate the speaker's meaning.
  - Deduplicate repeated phrases and looping hallucination artefacts.
  - Remove silence/tail hallucinations (e.g. YouTube outro phrases, repetitive loops).
  - Fix known phonetic recognition artefacts (e.g. 'exam text' -> 'exam tips').
  - Ensure word-level timestamps (for SRT) remain synchronized with text changes.
"""

import re
from typing import List, Dict, Tuple, Any

# ── 1. Known Silence / Prompt / Outro Hallucinations ─────────────────────────
HALLUCINATED_PHRASES = {
    # English Whisper hallucinations
    "thanks for watching",
    "thanks for watching.",
    "thank you for watching",
    "thank you for watching.",
    "please subscribe",
    "please subscribe.",
    "please like and subscribe",
    "subtitles by",
    "translated by",
    "copyright",
    "all rights reserved",
    "thank you very much",
    "thank you",
    "bye bye",
    # Urdu Whisper hallucinations
    "دیکھنے کا شکریہ",
    "سبسکرائب کریں",
    "شکریہ",
    # Roman Urdu
    "dekhne ka shukriya",
    "subscribe karein",
}

# ── 2. Known Recognition Artefacts & Confirmed Substitutions ────────────────
# Each rule is: (pattern, replacement, regex_flags)
# Applied to both Urdu script and Roman representations where appropriate.
URDU_SCRIPT_FIXES: List[Tuple[str, str]] = [
    # Confirmed in handoff: 'extreme request ki base kay uper'
    # Whisper heard 'بیٹ کی اوپر' or 'بیٹ کے اوپر'
    (r"بیٹ\s+(کی|کے)\s+اوپر", "base ke upar"),
    # Confirmed in handoff: 'exam tips'
    # Whisper heard 'ایگزام ٹیکسٹ' (exam text)
    (r"ایگزام\s+ٹیکسٹ", "exam tips"),
    # Phonetic mishear: 'ایمپورٹنڈی' -> 'importantly'
    (r"ایمپورٹنڈی", "importantly"),
    # Phonetic mishear: 'ایزیو نو' or 'ایسی نو' -> 'as you know'
    (r"(ایزیو\s+نو|ایسی\s+نو)", "as you know"),
    # Phonetic mishear: 'میریجمنٹ' -> 'management'
    (r"میریجمنٹ", "management"),
    # Entity correction: Scans -> SKANS
    (r"\bScans\b", "SKANS"),
    (r"\bscans\b", "SKANS"),
    # User confirmed: 'tou I hope...'
    (r"آئی\s+ہوپ", "I hope"),
    # Phonetic mishears in Pakistani lecture audio
    (r"دیکھنکو\s+سر", "Thank you sir"),
    (r"دیکھنکو", "Thank you"),
    (r"رہن\s+(پہ|پر|پی)\s+کلک", "link pe click"),
    (r"نیکس\s+فیک\s+پیپر", "next paper"),
    (r"کون\s+کو\s+بیپر", "kon sa paper"),
    (r"فائنینچل\s+منیجمنٹ", "Financial Management"),
    (r"فی\s+آف\s+چارج", "free of charge"),
    (r"اس\s+کے\s+اہم\s+ہی\s+campus", "SKANS campus"),
    (r"پیٹے\s+پریشان\s+کیوں\s+بیٹھے\s+لے\s+ہو", "بیٹے پریشان کیوں بیٹھے ہو"),
    (r"\bپیٹے\s+پریشان\b", "بیٹے پریشان"),
    (r"فیس\s+نہیں\s+آگی", "فیس نہیں لگے گی"),
]

ROMAN_URDU_FIXES: List[Tuple[str, str]] = [
    # Confirmed in handoff: 'extreme request ki base kay uper'
    (r"\bbase\s+ki\s+upar\b", "base kay uper"),
    (r"\bbase\s+ke\s+upar\b", "base kay uper"),
    (r"\bbait\s+(ki|ke)\s+upar\b", "base kay uper"),
    # Confirmed in handoff: 'exam tips'
    (r"\bexam\s+text\b", "exam tips"),
    # User confirmed: 'ki Tarah exam tips pay baat hogi'
    (r"\bki\s+tarah\s+exam\s+tips\s+(peh|pay)\b", "ki Tarah exam tips pay"),
    (r"\bki\s+tarah\b", "ki Tarah"),
    (r"\bpeh\b", "pay"),
    # User confirmed: 'tou hum us riwayat'
    (r"\b(to|tou)\s+hum\s+is\s+riwayat\b", "tou hum us riwayat"),
    (r"\bis\s+riwayat\b", "us riwayat"),
    # User confirmed: 'tou I hope to join you all in this session. To join it, please click on the link below.'
    (r"\b(to|tou)\s+aayi\s+hope\b", "tou I hope"),
    (r"\baayi\s+hope\b", "I hope"),
    (r"\btou\s+join\b", "to join"),
    (r"\b(to|tou)\s+join\s+you\s+all\s+(in\s+)?this\s+session\s+(to|tou)\s+join\s+it\s+please\s+click\s+on\s+the\s+link\s+below\b",
     "tou I hope to join you all in this session. To join it, please click on the link below."),
    (r"\b(to|tou)\s+join\s+you\s+all\s+this\s+session\b", "to join you all in this session"),
    # Common mis-transcriptions in Roman
    (r"\baslam\s+alaikum\b", "asalam alaikum"),
    (r"\baslam\b", "asalam"),
    (r"\beasy\s+no\b", "as you know"),
    (r"\bimportantdy\b", "importantly"),
    # Entity correction: Scans -> SKANS
    (r"\bScans\b", "SKANS"),
    (r"\bscans\b", "SKANS"),
    # Phonetic mishear fixes in Roman Urdu
    (r"\bdikhnko\s+sar\b", "Thank you sir"),
    (r"\bdikhnko\b", "Thank you"),
    (r"\brhn\s+(pay|pe|par)\s+click\b", "link pe click"),
    (r"\bniks\s+fik\s+paper\b", "next paper"),
    (r"\bkon\s+ko\s+bipr\b", "kon sa paper"),
    (r"\bfayninchl\s+mnijmnt\b", "Financial Management"),
    (r"\bfi\s+aaf\s+charj\b", "free of charge"),
    (r"\bpitay\s+prishan\s+kion\s+bithay\s+lay\s+ho\b", "betay pareshan kion baithay ho"),
    (r"\bpitay\s+prishan\b", "betay pareshan"),
    (r"\bpitay\b", "betay"),
    (r"\bprishan\b", "pareshan"),
    (r"\bbithay\s+lay\s+ho\b", "baithay ho"),
    (r"\bfees\s+nahi\s+aagi\b", "fees nahi lagay gi"),
]


# Multi-word replacements for word-level tokens
# Format: (tuple_of_target_words, tuple_of_replacement_words)
WORD_PHRASE_REPLACEMENTS: List[Tuple[Tuple[str, ...], Tuple[str, ...]]] = [
    # 'ایگزام ٹیکسٹ' -> ('exam', 'tips')
    (("ایگزام", "ٹیکسٹ"), ("exam", "tips")),
    (("exam", "text"), ("exam", "tips")),
    # 'بیٹ کی اوپر' / 'بیٹ کے اوپر' -> ('base', 'ke', 'upar')
    (("بیٹ", "کی", "اوپر"), ("base", "ke", "upar")),
    (("بیٹ", "کے", "اوپر"), ("base", "ke", "upar")),
    (("base", "ki", "upar"), ("base", "kay", "uper")),
    (("base", "ke", "upar"), ("base", "kay", "uper")),
    # 'ایزیو نو' / 'ایسی نو' -> ('as', 'you', 'know')
    (("ایزیو", "نو"), ("as", "you", "know")),
    (("ایسی", "نو"), ("as", "you", "know")),
    (("easy", "no"), ("as", "you", "know")),
    # User corrections: 'is riwayat' -> 'us riwayat'
    (("is", "riwayat"), ("us", "riwayat")),
    # User corrections: 'aayi hope' -> 'I hope'
    (("آئی", "ہوپ"), ("I", "hope")),
    (("aayi", "hope"), ("I", "hope")),
    # Single words
    (("ایمپورٹنڈی",), ("importantly",)),
    (("میریجمنٹ",), ("مینجمنٹ",)),
    (("scans",), ("SKANS",)),
    (("Scans",), ("SKANS",)),
    (("peh",), ("pay",)),
    (("aslam",), ("asalam",)),
    (("Aslam",), ("asalam",)),
]


def clean_word_objects(words: List[Any]) -> List[Any]:
    """
    Cleans a list of Whisper word objects (preserving word.start and word.end):
      1. Replaces known misrecognized phrases/words with their corrected tokens.
      2. Removes back-to-back duplicate words and 2-grams (loops).
    """
    if not words:
        return words

    # 1. Apply multi-word replacements
    i = 0
    new_words = []
    while i < len(words):
        matched = False
        for target_tuple, repl_tuple in WORD_PHRASE_REPLACEMENTS:
            t_len = len(target_tuple)
            if i + t_len <= len(words):
                candidate = tuple(
                    re.sub(r"[^\w\u0600-\u06FF]", "", words[i + k].word).strip().lower()
                    for k in range(t_len)
                )
                if candidate == target_tuple:
                    # Matched! Distribute replacement words over the time span
                    start_time = words[i].start
                    end_time = words[i + t_len - 1].end
                    duration = max(0.01, end_time - start_time)
                    r_len = len(repl_tuple)

                    # Create updated word objects
                    # We can clone the existing class or use an object with start, end, word attributes
                    WordClass = type(words[i])
                    for r_idx, r_word in enumerate(repl_tuple):
                        w_start = start_time + (r_idx * duration / r_len)
                        w_end = start_time + ((r_idx + 1) * duration / r_len)
                        try:
                            new_w = WordClass(start=w_start, end=w_end, word=r_word, probability=1.0)
                        except Exception:
                            # In case WordClass constructor differs
                            new_w = words[i]
                            new_w.word = r_word
                            new_w.start = w_start
                            new_w.end = w_end
                        new_words.append(new_w)

                    i += t_len
                    matched = True
                    break
        if not matched:
            new_words.append(words[i])
            i += 1

    # 2. Deduplicate consecutive word loops
    if len(new_words) < 2:
        return new_words

    deduped = []
    i = 0
    while i < len(new_words):
        w_clean = re.sub(r"[^\w\u0600-\u06FF]", "", new_words[i].word).strip().lower()
        # Single word loop (e.g. "yes yes")
        if deduped and re.sub(r"[^\w\u0600-\u06FF]", "", deduped[-1].word).strip().lower() == w_clean and len(w_clean) > 1:
            i += 1
            continue
        # 2-gram loop (e.g. "dekhein ge dekhein ge")
        if len(deduped) >= 2 and i + 1 < len(new_words):
            prev = (
                re.sub(r"[^\w\u0600-\u06FF]", "", deduped[-2].word).strip().lower(),
                re.sub(r"[^\w\u0600-\u06FF]", "", deduped[-1].word).strip().lower(),
            )
            curr = (
                re.sub(r"[^\w\u0600-\u06FF]", "", new_words[i].word).strip().lower(),
                re.sub(r"[^\w\u0600-\u06FF]", "", new_words[i+1].word).strip().lower(),
            )
            if prev == curr:
                i += 2
                continue

        deduped.append(new_words[i])
        i += 1

    return deduped

def is_repetition_loop(text: str) -> bool:
    """
    Detect if text contains a degenerate repetition loop, e.g.:
      - 'J-A-J-A-J-A'
      - 'dekhein ge dekhein ge dekhein ge dekhein ge'
      - 'دیکھیں گے دیکھیں گے دیکھیں گے'
    """
    clean = text.strip()
    if not clean:
        return False

    # Short string with very few distinct characters
    if len(clean) > 25 and len(set(clean.lower())) < 8:
        return True

    words = clean.split()
    n = len(words)
    if n < 3:
        return False

    # 1-gram repetition: e.g. "yes yes yes"
    for i in range(n - 2):
        if words[i].lower() == words[i+1].lower() == words[i+2].lower():
            return True

    # 2-gram repetition: e.g. "dekhein ge dekhein ge dekhein ge"
    if n >= 4:
        for i in range(n - 3):
            if (words[i].lower() == words[i+2].lower() and 
                words[i+1].lower() == words[i+3].lower()):
                return True

    return False


def deduplicate_consecutive_words(words: List[str]) -> List[str]:
    """
    Remove back-to-back duplicate n-grams (1-gram, 2-gram, 3-gram).
    Example:
      ['dekhein', 'ge', 'dekhein', 'ge', 'dekhein', 'ge'] -> ['dekhein', 'ge']
    """
    if len(words) < 2:
        return words

    result = list(words)
    changed = True

    # Run passes until no further duplicate n-grams are collapsed
    while changed:
        changed = False
        n = len(result)

        # Check n-grams of length 3, 2, 1
        for gram_len in (3, 2, 1):
            if gram_len * 2 > n:
                continue
            i = 0
            new_res = []
            while i < len(result):
                # Check if current chunk matches the chunk right before it in new_res
                if len(new_res) >= gram_len:
                    prev_chunk = [w.lower().strip(".,!?") for w in new_res[-gram_len:]]
                    curr_chunk = [w.lower().strip(".,!?") for w in result[i:i+gram_len]]
                    if prev_chunk == curr_chunk and len(curr_chunk) == gram_len:
                        # Skip duplicate chunk
                        i += gram_len
                        changed = True
                        continue
                new_res.append(result[i])
                i += 1
            result = new_res
            if changed:
                break

    return result


# ── 4. Segment-Level Cleaning (Preserves Timestamps for SRT) ────────────────

class CleanSegment:
    """A wrapper for transcript segments with word-level timestamps."""
    def __init__(self, start: float, end: float, text: str, words: List[Any] = None):
        self.start = start
        self.end = end
        self.text = text
        self.words = words or []


def clean_segments(segments: List[Any]) -> List[Any]:
    """
    Process raw Whisper segment objects:
      1. Backwards tail pruning: strips trailing hallucinated loops / silence noise.
      2. Drops empty or pure hallucination outro segments.
      3. Applies recognition artefact fixes & word deduplication while keeping timestamps.
      4. Updates segment text to match cleaned words.
    """
    if not segments:
        return []

    # 1. Backwards tail pruning: remove trailing hallucinations on silence/music
    # Whisper commonly hallucinates repetitively or with very low logprob at the audio tail
    result = list(segments)
    while result:
        last_seg = result[-1]
        text = last_seg.text.strip()
        norm_text = re.sub(r"[^\w\s]", "", text.lower()).strip()
        avg_logprob = getattr(last_seg, 'avg_logprob', 0.0)
        no_speech_prob = getattr(last_seg, 'no_speech_prob', 0.0)

        is_outro_phrase = norm_text in HALLUCINATED_PHRASES
        is_loop = is_repetition_loop(text)
        is_silence = no_speech_prob > 0.7
        # Only prune if it is an outro phrase, a repetitive loop, or degenerate low-confidence noise.
        # This prevents dropping genuine code-switched English closing remarks.
        is_degenerate = (avg_logprob < -1.5 and len(norm_text.split()) < 4) or (avg_logprob < -1.2 and is_loop)

        if is_outro_phrase or is_loop or is_silence or is_degenerate:
            result.pop()
        else:
            break

    # 2. Process remaining segments
    cleaned_segs = []
    for seg in result:
        text = seg.text.strip()
        words = getattr(seg, 'words', None) or []

        norm_text = re.sub(r"[^\w\s]", "", text.lower()).strip()
        if norm_text in HALLUCINATED_PHRASES:
            continue

        if words:
            cleaned_words = clean_word_objects(words)
            if not cleaned_words:
                continue
            seg.words = cleaned_words
            seg.text = " ".join(w.word.strip() for w in cleaned_words)
        else:
            seg.text = clean_urdu_text(seg.text)

        cleaned_segs.append(seg)

    return cleaned_segs


# ── 5. Text-Level Cleaning ──────────────────────────────────────────────────

def clean_urdu_text(text: str) -> str:
    """
    Applies conservative cleanup to Urdu script / mixed text:
      - Applies confirmed phonetic artefact fixes (e.g. 'بیٹ کی اوپر' -> 'base ke upar')
      - Deduplicates repeated phrases
      - Normalizes punctuation spacing
    """
    # 1. Phonetic fixes
    res = text
    for pattern, repl in URDU_SCRIPT_FIXES:
        res = re.sub(pattern, repl, res)

    # 2. Word-level deduplication
    words = res.split()
    words = deduplicate_consecutive_words(words)
    res = " ".join(words)

    # 3. Punctuation cleanup
    res = re.sub(r"\s+([,.:;?!،۔])", r"\1", res)  # remove space before punctuation
    res = re.sub(r"([,.:;?!،۔])(?=[^\s,.:;?!،۔])", r"\1 ", res)  # ensure space after

    return res.strip()


def clean_roman_text(text: str) -> str:
    """
    Applies conservative cleanup to Roman Urdu / English text:
      - Applies persistent user library overrides from preferences.json
      - Applies confirmed phonetic artefact fixes (e.g. 'exam text' -> 'exam tips')
      - Deduplicates repeated phrases
      - Normalizes punctuation spacing and casing
    """
    res = text

    # 0. User Library Overrides (saved via UI "Add to Library")
    try:
        from roman_urdu import get_preferences
        prefs = get_preferences()
        for k, v in prefs.items():
            if re.match(r"^[A-Za-z0-9\s\-]+$", k):
                pattern = r"\b" + re.escape(k) + r"\b"
                res = re.sub(pattern, v, res, flags=re.IGNORECASE)
    except Exception:
        pass

    # 1. Phonetic fixes
    for pattern, repl in ROMAN_URDU_FIXES:
        res = re.sub(pattern, repl, res, flags=re.IGNORECASE)

    # 2. Word-level deduplication
    words = res.split()
    words = deduplicate_consecutive_words(words)
    res = " ".join(words)

    # 3. Punctuation cleanup
    res = re.sub(r"\s+([,.:;?!])", r"\1", res)
    res = re.sub(r"([,.:;?!])(?=[^\s,.:;?!])", r"\1 ", res)

    return res.strip()


def clean_roman_text_in_srt(srt_text: str) -> str:
    """
    Applies clean_roman_text strictly to subtitle text lines in an SRT file,
    preserving all SRT sequence numbers, timestamp markers, and line breaks.
    """
    lines = srt_text.splitlines(keepends=True)
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped.isdigit() or '-->' in stripped or stripped == '':
            out.append(line)
        else:
            out.append(clean_roman_text(stripped) + '\n')
    return ''.join(out)


# ── Quick Verification ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    test_urdu = "اسلام علیکم ہم نے ایگزام ٹیکسٹ کروایا بیٹ کی اوپر اور ایمپورٹنڈی ایسی نو دیکھیں گے دیکھیں گے دیکھیں گے"
    print("Urdu input :", test_urdu)
    print("Urdu clean :", clean_urdu_text(test_urdu))

    test_roman = "aslam alaikum extreme request ki base ki upar exam text easy no dekhein ge dekhein ge dekhein ge"
    print("\nRoman input :", test_roman)
    print("Roman clean :", clean_roman_text(test_roman))
