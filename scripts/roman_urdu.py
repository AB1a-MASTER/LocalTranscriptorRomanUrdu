"""
roman_urdu.py
=============
Conservative local Urdu-to-Roman-Urdu transliteration.

Strategy (in priority order):
  1. Latin-script tokens  → pass through unchanged (English words).
  2. Dictionary lookup    → exact match for common Urdu words and
                            English loanwords spelled in Urdu script.
  3. Character map        → position-aware letter-by-letter fallback
                            for unknown words.

Design is deliberately conservative:
  - Prefer recognisable output over clever guessing.
  - Ambiguous short vowels are omitted rather than guessed wrong.
  - English loanwords in Urdu script (ایگزام, مینجمنٹ, etc.) are
    restored to their English spellings via the dictionary.
  - Punctuation and whitespace are always preserved.

Public API
----------
    transliterate(text: str) -> str
        Convert a mixed Urdu-script / Latin-script string to Roman Urdu.
        English words are left unchanged.

    transliterate_word(word: str) -> str
        Transliterate a single token (strips, converts, re-attaches
        leading / trailing punctuation).
"""

import re
import unicodedata
import json
import functools
from pathlib import Path

# Try importing extended lexicon and morphological affix rules
try:
    from urdu_lexicon import URDU_LEXICON, PREFIXES, SUFFIXES
except ImportError:
    try:
        from scripts.urdu_lexicon import URDU_LEXICON, PREFIXES, SUFFIXES
    except ImportError:
        URDU_LEXICON = {}
        PREFIXES = []
        SUFFIXES = []

_PREFS_FILE = Path(__file__).resolve().parent / "preferences.json"


def _nfc(s: str) -> str:
    """NFC-normalise so different Unicode forms of the same Urdu letter match."""
    return unicodedata.normalize('NFC', s)


# ════════════════════════════════════════════════════════════════════════════
# USER SPELLING PREFERENCES
# ════════════════════════════════════════════════════════════════════════════
#
# Edit this dict to lock in your preferred spellings for specific Urdu words.
# These override EVERYTHING — dictionary, character map, all of it.
# Keys are Urdu script words; values are your preferred Roman spelling.
#
# Examples of common Pakistani spelling choices:
#   گے  → many write "gay"  (others: "ge", "gey")
#   گی  → many write "gee"  (others: "gi",  "gi")
#   ہے  → many write "hai"  (others: "hay", "he")
#   ہیں → many write "hain" (others: "hen", "hein")
#   ہوئے→ many write "huey" (others: "hue", "hoey")
#   نہیں→ many write "nahi" (others: "nay", "nahin")
#   کیا → many write "kia"  (others: "kiya", "kya")
#   بھی → many write "bhi"  (others: "bi",  "bhee")
#   تھا → many write "tha"  (others: "thaa", "ta")
#   تھے → many write "thay" (others: "the",  "they")
#
# To add a preference: 'Urdu word': 'your spelling',
# To remove a preference: delete or comment out the line.
# ────────────────────────────────────────────────────────────────────────────
SPELLING_PREFS: dict[str, str] = {
    # ── User active preferences ───────────────────────────────────────────
    'تو':     'tou',     # preferred over "to"
    'پہ':     'pay',     # preferred over "peh"
    'طرح':    'Tarah',   # preferred over "tarah"
    'اسلام':  'asalam',  # preferred over "aslam"
    'السلام': 'asalam',  # preferred over "assalam"

    # ── Additional common preference options (uncomment to activate) ──────
    # 'گے':  'gay',    # future masculine plural — uncomment to prefer "gay"
    # 'گی':  'gee',   # future feminine singular — uncomment to prefer "gee"
    # 'گا':  'ga',    # future masculine singular
    # 'ہے':  'hay',   # is — uncomment to prefer "hay" over "hai"
    # 'کیا': 'kia',   # did — uncomment to prefer "kia" over "kiya"
    # 'ہوئے':'huey',  # happened — uncomment to prefer "huey" over "hue"
}
# ════════════════════════════════════════════════════════════════════════════

# ── Unicode ranges ────────────────────────────────────────────────────────
_URDU_RE  = re.compile(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]')
_LATIN_RE = re.compile(r'^[A-Za-z]')   # word starts with Latin letter


def _has_urdu(s: str) -> bool:
    return bool(_URDU_RE.search(s))


# ── Aspiration pairs: consonant immediately followed by ھ ─────────────────
# Do-chashmi-he (ھ U+06BE) marks aspiration in Urdu.
_ASPIRATED: dict[str, str] = {
    'ب': 'bh', 'پ': 'ph', 'ت': 'th', 'ٹ': 'th',
    'ج': 'jh', 'چ': 'chh',
    'د': 'dh', 'ڈ': 'dh',
    'ک': 'kh', 'گ': 'gh',
    'ل': 'lh', 'ر': 'rh', 'ن': 'nh',
}

# ── Character map — position-unaware base ─────────────────────────────────
# Used for unknown words after dictionary lookup fails.
# Vowel characters (ا و ی ے) are handled position-aware in _char_map_word().
_BASE: dict[str, str] = {
    # Alifs
    'آ': 'aa', 'أ': 'a', 'إ': 'a', 'ٱ': 'a',
    # Consonants
    'ب': 'b',  'پ': 'p',  'ت': 't',  'ٹ': 't',
    'ث': 's',  'ج': 'j',  'چ': 'ch',
    'ح': 'h',  'خ': 'kh',
    'د': 'd',  'ڈ': 'd',  'ذ': 'z',
    'ر': 'r',  'ڑ': 'r',  'ز': 'z',  'ژ': 'zh',
    'س': 's',  'ش': 'sh',
    'ص': 's',  'ض': 'z',  'ط': 't',  'ظ': 'z',
    'ع': 'a',  'غ': 'gh',
    'ف': 'f',  'ق': 'q',
    'ک': 'k',  'گ': 'g',
    'ل': 'l',  'م': 'm',
    'ن': 'n',  'ں': 'n',
    'ہ': 'h',  'ھ': 'h',  'ه': 'h',
    'ی': 'i',  'ے': 'ay',
    'ئ': 'y',  'ء': '',   'ؤ': 'o',  'ة': 'a',
    # Diacritics (usually absent from Whisper output; handle if present)
    '\u064E': 'a',   # fatha  (zabar)
    '\u064F': 'u',   # damma  (pesh)
    '\u0650': 'i',   # kasra  (zer)
    '\u0651': '',    # shadda (tashdeed)
    '\u0652': '',    # sukun
    '\u0653': 'aa',  # madd
    '\u0654': '',    # hamza above
    '\u0655': '',    # hamza below
    '\u0670': 'a',   # superscript alef
}

# ── Dictionary ────────────────────────────────────────────────────────────
# Entries are lower-cased at lookup time so keys must be lower-case.
# Add project-specific corrections here rather than modifying the char map.

DICTIONARY: dict[str, str] = {
    # ── Greetings & common phrases ────────────────────────────────────────
    'ہیلو': 'hello',
    'اسلام': 'asalam',
    'علیکم': 'alaikum',
    'اسلام علیکم': 'asalam alaikum',
    'السلام علیکم': 'assalam alaikum',

    # ── Pronouns ──────────────────────────────────────────────────────────
    'میں': 'mein',    'ہم': 'hum',    'آپ': 'aap',
    'تم': 'tum',      'وہ': 'woh',    'یہ': 'yeh',
    'ان': 'un',       'اس': 'is',     'اسی': 'isi',
    'اسے': 'isay',    'انہیں': 'unhein', 'انکا': 'unka',
    'ہمارا': 'hamara', 'ہمارے': 'hamare', 'ہماری': 'hamari',
    'آپکا': 'aapka',  'آپکی': 'aapki', 'آپکے': 'aapke',
    'مجھے': 'mujhe',  'مجھ': 'mujh',  'ہمیں': 'humein',

    # ── Postpositions & conjunctions ──────────────────────────────────────
    'کا': 'ka',   'کی': 'ki',   'کے': 'ke',
    'کو': 'ko',   'سے': 'se',   'میں': 'mein',
    'پر': 'par',  'پہ': 'peh',  'نے': 'ne',
    'اور': 'aur', 'یا': 'ya',   'لیکن': 'lekin',
    'کہ': 'ke',   'جو': 'jo',   'جس': 'jis',
    'جیسے': 'jaise', 'جیسا': 'jaisa', 'جیسی': 'jaisi',
    'تاکہ': 'taake', 'اگر': 'agar', 'تو': 'to',
    'مگر': 'magar', 'بلکہ': 'balke',
    'جب': 'jab',  'جہاں': 'jahan', 'جبکہ': 'jabke',
    'کیونکہ': 'kyunke',
    'ساتھ': 'saath', 'بغیر': 'baghair',
    'تک': 'tak',  'میں سے': 'mein se',

    # ── Verbs — common forms ──────────────────────────────────────────────
    'ہے': 'hai',      'ہیں': 'hain',    'ہی': 'hi',
    'ہو': 'ho',       'ہوں': 'hun',     'ہوا': 'hua',
    'ہوئے': 'hue',    'ہوئی': 'hui',    'ہونا': 'hona',
    'ہوتا': 'hota',   'ہوتی': 'hoti',   'ہوتے': 'hote',
    'ہوگا': 'hoga',   'ہوگی': 'hogi',   'ہوگے': 'honge',
    'ہوں گے': 'honge',
    'گے': 'ge',       'گی': 'gi',       'گا': 'ga',
    'کر': 'kar',      'کرنا': 'karna',  'کرتے': 'karte',
    'کرتا': 'karta',  'کرتی': 'karti',  'کریں': 'karein',
    'کرو': 'karo',    'کیا': 'kiya',    'کی': 'ki',
    'کروایا': 'karwaya', 'کروائیں': 'karwayein',
    'کروائیں گے': 'karwayein ge',
    'کرتے ہوئے': 'karte hue',
    'رہا': 'raha',    'رہی': 'rahi',    'رہے': 'rahe',
    'رہیں': 'rahein', 'رہا ہے': 'raha hai',
    'رہے ہیں': 'rahe hain',
    'آنا': 'aana',    'آیا': 'aaya',    'آئی': 'aayi',
    'آئے': 'aaye',    'آئیں': 'aayein',
    'جانا': 'jaana',  'گیا': 'gaya',    'گئی': 'gayi',
    'گئے': 'gaye',    'جاتے': 'jate',   'جائے': 'jaye',
    'جائیں': 'jayein',
    'دینا': 'dena',   'دیا': 'diya',    'دیتے': 'dete',
    'دیں': 'dein',    'دیتا': 'deta',
    'لینا': 'lena',   'لیا': 'liya',    'لیتے': 'lete',
    'ملنا': 'milna',  'ملا': 'mila',    'ملتے': 'milte',
    'ملیں': 'milein',
    'ملے': 'mile',
    'چاہنا': 'chahna', 'چاہیے': 'chahiye', 'چاہتا': 'chahta',
    'سمجھنا': 'samajhna', 'سمجھیں': 'samjhein',
    'بتانا': 'batana', 'بتائیں': 'batayen', 'بتایا': 'bataya',
    'بنانا': 'banana', 'بنایا': 'banaya', 'بنتا': 'banta',
    'پڑھنا': 'parhna', 'پڑھیں': 'parhein', 'پڑھا': 'parha',
    'لکھنا': 'likhna', 'لکھیں': 'likhein',
    'سننا': 'sunna',  'سنیں': 'sunein',
    'دیکھنا': 'dekhna', 'دیکھیں': 'dekhein', 'دیکھا': 'dekha',
    'کھولنا': 'kholna', 'کھولیں': 'kholein',
    'کلک': 'click',   # loanword

    # ── Nouns — common ────────────────────────────────────────────────────
    'بات': 'baat',    'باتیں': 'batein', 'باتوں': 'baton',
    'کام': 'kaam',    'کاموں': 'kamon',
    'وقت': 'waqt',    'دن': 'din',      'رات': 'raat',
    'پیسہ': 'paisa',  'پیسے': 'paise',
    'بچہ': 'bachcha', 'بچے': 'bachche', 'بچوں': 'bachchon',
    'آدمی': 'aadmi',  'عورت': 'aurat',
    'گھر': 'ghar',    'دفتر': 'daftar',
    'لوگ': 'log',     'لوگوں': 'logon',
    'روایت': 'riwayat',
    'دفعہ': 'dafa',   'دفعے': 'dafay',
    'طرح': 'tarah',
    'ساری': 'saari',  'سارا': 'saara', 'سارے': 'saare',
    'پیپر': 'paper',  'پیپرز': 'papers',
    'پاس': 'paas',
    'بعد': 'baad',
    'مزید': 'mazeed',
    'لنک': 'link',    # loanword
    'اوپر': 'upar',
    'نیچے': 'neeche',
    'بیچ': 'beech',
    'بیٹ': 'base',    # contextual: "bait ki upar" = "base ke upar"

    # ── Adjectives / adverbs ──────────────────────────────────────────────
    'بہت': 'bohat',   'کم': 'kam',      'زیادہ': 'zyada',
    'اچھا': 'acha',   'اچھی': 'achi',   'اچھے': 'ache',
    'برا': 'bura',    'بری': 'buri',    'برے': 'bure',
    'بڑا': 'bara',    'بڑی': 'bari',    'بڑے': 'bare',
    'چھوٹا': 'chota', 'چھوٹی': 'choti', 'چھوٹے': 'chote',
    'نیا': 'naya',    'نئی': 'nayi',    'نئے': 'naye',
    'پرانا': 'purana', 'پرانی': 'purani',
    'ضروری': 'zaroori',
    'خاص': 'khaas',   'مشکل': 'mushkil', 'آسان': 'aasaan',
    'صرف': 'sirf',    'بالکل': 'bilkul', 'شاید': 'shayad',
    'پہلے': 'pehle',  'پہلی': 'pehli',  'پہلا': 'pehla',
    'آگے': 'aage',    'پیچھے': 'peeche',
    'ابھی': 'abhi',   'اب': 'ab',       'پھر': 'phir',
    'سب': 'sab',      'سبھی': 'sabhi',
    'کبھی': 'kabhi',  'کبھی کبھی': 'kabhi kabhi',
    'ہاں': 'haan',    'نہیں': 'nahi',   'نہ': 'na',
    'بھی': 'bhi',     'ٹھیک': 'theek',

    # ── Numbers (Urdu script) ──────────────────────────────────────────────
    'ایک': 'ek',  'دو': 'do',   'تین': 'teen', 'چار': 'char',
    'پانچ': 'paanch', 'چھ': 'chhe', 'سات': 'saat', 'آٹھ': 'aath',
    'نو': 'no',   'دس': 'das',

    # ── Urdu letter names (for spoken abbreviations like AFM, FM) ─────────
    # 'کے' is intentionally excluded — it's primarily the postposition 'ke'.
    # 'آئی' maps to 'I'; 'یو' maps to 'you' (both handled as loanwords below).
    'اے': 'A',  'بی': 'B',  'سی': 'C',  'ڈی': 'D',
    'ای': 'E',  'ایف': 'F',  'جی': 'G',  'ایچ': 'H',
    'جے': 'J',              'ایل': 'L',
    'ایم': 'M', 'این': 'N',              'پی': 'P',
    'کیو': 'Q', 'آر': 'R',  'ایس': 'S',  'ٹی': 'T',
    'وی': 'V',  'ڈبلیو': 'W', 'ایکس': 'X',
    'وائی': 'Y', 'زیڈ': 'Z',

    # ── English loanwords (Urdu script → English) ─────────────────────────
    # Education / professional
    'ایگزام': 'exam',          'ایگزامز': 'exams',
    'ہیک': 'hack',             'ہیکس': 'hacks',
    'سیشن': 'session',         'سیشنز': 'sessions',
    'ٹیکسٹ': 'text',           'ٹیکنیک': 'technique',
    'ٹیکنیکس': 'techniques',   'ٹیکنیکل': 'technical',
    'ٹپس': 'tips',             'ٹپ': 'tip',
    'ایڈوانس': 'advance',      'ایڈوانسڈ': 'advanced',
    'فائننشل': 'financial',    'مینجمنٹ': 'management',
    'پروفیشنل': 'professional',
    'مارکس': 'marks',          'مارکنگ': 'marking',
    'پرفارمنس': 'performance',  'اسائنمنٹ': 'assignment',
    'پریزنٹیشن': 'presentation',
    'سپٹیمبر': 'september',    'اکتوبر': 'october',
    'نومبر': 'november',       'دسمبر': 'december',
    'جنوری': 'january',        'فروری': 'february',
    'مارچ': 'march',           'اپریل': 'april',
    'مئی': 'may',              'جون': 'june',
    'جولائی': 'july',          'اگست': 'august',
    'کانٹینیو': 'continue',    'کنٹینیو': 'continue',
    'کنٹینیوز': 'continues',
    'ریسپانس': 'response',     'اپریشیٹ': 'appreciate',
    'ایمپورٹنٹ': 'important',   'ایمپورٹنٹلی': 'importantly',
    'ایمپورٹنڈی': 'importantly',  # likely mis-transcription of "importantly"
    'ایزی': 'easy',            'ایزیو': 'easy',  # likely mis-transcription
    'ڈیفینیٹلی': 'definitely',  'بیسیکلی': 'basically',
    'آفیشلی': 'officially',    'اسپیشلی': 'specially',
    'نارملی': 'normally',      'جنرلی': 'generally',
    'ٹوٹل': 'total',           'فائنل': 'final',
    'ڈیٹیل': 'detail',         'ڈیٹیلز': 'details',
    'پوائنٹ': 'point',         'پوائنٹس': 'points',
    'ٹاپک': 'topic',           'ٹاپکس': 'topics',
    'کوئسچن': 'question',      'کوئسچنز': 'questions',
    'آنسر': 'answer',          'آنسرز': 'answers',
    'نوٹس': 'notes',           'نوٹ': 'note',
    'چیپٹر': 'chapter',        'چیپٹرز': 'chapters',
    'فارمولا': 'formula',      'فارمولے': 'formulae',
    'کیلکولیشن': 'calculation', 'کیلکولیشنز': 'calculations',
    'پریکٹس': 'practice',      'پریکٹیکل': 'practical',
    'تھیوری': 'theory',
    'اسٹوڈنٹ': 'student',      'اسٹوڈنٹس': 'students',
    'ٹیچر': 'teacher',         'لیکچرر': 'lecturer',
    'کلاس': 'class',           'کلاسز': 'classes',
    'آن لائن': 'online',       'آف لائن': 'offline',
    'ویبینار': 'webinar',       'سیمینار': 'seminar',
    'ریکارڈنگ': 'recording',   'ریکارڈ': 'record',
    'لائیو': 'live',           'لائنک': 'link',
    'لنک': 'link',             'کلک': 'click',
    'پورٹل': 'portal',         'پلیٹ فارم': 'platform',
    'یوٹیوب': 'youtube',       'واٹس ایپ': 'whatsapp',
    # Finance / ACCA
    'پروفٹ': 'profit',         'لوس': 'loss',
    'ریونیو': 'revenue',       'کاسٹ': 'cost',
    'بیلنس': 'balance',        'شیٹ': 'sheet',
    'کیش فلو': 'cash flow',    'کیش': 'cash',
    'ڈیویڈنڈ': 'dividend',     'ایکوئٹی': 'equity',
    'ڈیٹ': 'debt',             'لون': 'loan',
    'ٹیکس': 'tax',             'ٹیکسیشن': 'taxation',
    'آڈٹ': 'audit',           'آڈیٹر': 'auditor',
    'اکاؤنٹ': 'account',       'اکاؤنٹنگ': 'accounting',
    'فنانس': 'finance',        'انویسٹمنٹ': 'investment',
    'پورٹ فولیو': 'portfolio',  'ایسٹ': 'asset',
    'لائبیلیٹی': 'liability',  'کیپیٹل': 'capital',
    # General loanwords
    'ہوپ': 'hope',             'جوائن': 'join',
    'آل': 'all',               'یو': 'you',  'آئی': 'aayi',
    'ریکویسٹ': 'request',      'شیئر': 'share',
    'ویڈیو': 'video',          'آڈیو': 'audio',
    'چینل': 'channel',         'گروپ': 'group',
    'ٹیم': 'team',             'پروجیکٹ': 'project',
    'پلان': 'plan',            'اسٹریٹجی': 'strategy',
    'سسٹم': 'system',          'پروسیس': 'process',
    'ڈیٹا': 'data',            'انفارمیشن': 'information',
    'رزلٹ': 'result',          'رزلٹس': 'results',
    'اپڈیٹ': 'update',         'اپڈیٹس': 'updates',
    'سپورٹ': 'support',        'فیڈبیک': 'feedback',
    'ریویو': 'review',         'ریویوز': 'reviews',
    'آفر': 'offer',            'ڈیل': 'deal',
}


# ── Fallback: character-level transliteration ─────────────────────────────

def _char_map_word(word: str) -> str:
    """
    Transliterate a single Urdu-script word using the NFC character map.
    Handles aspiration pairs, position-aware vowels, and diacritics.
    Input is NFC-normalised before processing.
    """
    word = _nfc(word)
    chars = list(word)
    n = len(chars)
    out = []
    i = 0
    do_chashmi = _nfc('ھ')   # U+06BE

    while i < n:
        c = chars[i]

        # 1. Aspiration: consonant immediately followed by ھ (U+06BE)
        if c in _ASPIRATED_NFC and i + 1 < n and chars[i + 1] == do_chashmi:
            out.append(_ASPIRATED_NFC[c])
            i += 2
            continue

        alif  = _nfc('ا')
        waw   = _nfc('و')
        yeh_f = _nfc('ی')   # FARSI YEH — mid-word vowel
        yeh_b = _nfc('ے')   # YEH BARREE — word-final
        ayn   = _nfc('ع')

        # 2. Position-aware vowels
        if c == alif:
            out.append('a')
            i += 1
            continue

        if c == waw:
            out.append('w' if i == 0 else 'o')
            i += 1
            continue

        if c == yeh_f:
            out.append('y' if i == 0 else 'i')
            i += 1
            continue

        if c == yeh_b:
            out.append('ay')
            i += 1
            continue

        # 3. ع — ayn: word-initial → 'a', otherwise suppress
        if c == ayn:
            out.append('a' if i == 0 else '')
            i += 1
            continue

        # 4. NFC base map
        mapped = _BASE_NFC.get(c)
        if mapped is not None:
            out.append(mapped)
        elif c.isascii():
            out.append(c)
        # else: unknown — drop silently

        i += 1

    return ''.join(out)


# ── Dynamic Preferences Management & NFC Lookup Tables ───────────────────

def get_preferences() -> dict[str, str]:
    """Returns the active spelling preferences (from preferences.json if present, merged with SPELLING_PREFS)."""
    prefs = dict(SPELLING_PREFS)
    if _PREFS_FILE.exists():
        try:
            with open(_PREFS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    prefs.update(loaded)
        except Exception:
            pass
    return prefs


def save_preferences(prefs: dict[str, str]):
    """Persist spelling preferences to preferences.json and refresh lookup tables."""
    with open(_PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)
    refresh_lookup_tables()


def refresh_lookup_tables():
    """Rebuild NFC-normalised lookup tables with the latest preferences."""
    global _DICT_NFC
    active_prefs = get_preferences()
    _DICT_NFC = {
        **{_nfc(k): v for k, v in URDU_LEXICON.items()},
        **{_nfc(k): v for k, v in DICTIONARY.items()},
        **{_nfc(k): v for k, v in active_prefs.items()},
    }


# Initial build of lookup tables
_DICT_NFC: dict[str, str] = {}
refresh_lookup_tables()

# Also NFC-normalise the aspiration and base maps
_ASPIRATED_NFC: dict[str, str] = {_nfc(k): v for k, v in _ASPIRATED.items()}
_BASE_NFC: dict[str, str]      = {_nfc(k): v for k, v in _BASE.items()}

# ── Neural Transliteration Engine (Lazy initialized) ──────────────────────
_XLIT_ENGINE = None
_XLIT_INITIALIZED = False


@functools.lru_cache(maxsize=10000)
def _neural_transliterate(word_nfc: str) -> str | None:
    """
    Calls AI4Bharat IndicXlit transliteration engine if installed and initialized.
    Returns Roman Urdu prediction or None.
    """
    global _XLIT_ENGINE, _XLIT_INITIALIZED
    if not _XLIT_INITIALIZED:
        _XLIT_INITIALIZED = True
        try:
            # Dynamically import so static linters (e.g. Pyrefly, Pylance) do not flag missing optional dependency
            import importlib
            xlit_mod = importlib.import_module("ai4bharat.transliteration")
            xlit_cls = getattr(xlit_mod, "XlitEngine", None)
            if xlit_cls is not None:
                _XLIT_ENGINE = xlit_cls("ur", src_script_type="indic")
            else:
                _XLIT_ENGINE = None
        except Exception:
            _XLIT_ENGINE = None

    if _XLIT_ENGINE is not None:
        try:
            res = _XLIT_ENGINE.translit_word(word_nfc, topk=1)
            if isinstance(res, dict) and "ur" in res and res["ur"]:
                return res["ur"][0]
            elif isinstance(res, list) and res:
                return res[0]
        except Exception:
            pass
    return None


def _morphological_decompose(word_nfc: str) -> str | None:
    """
    Attempt to decompose an unknown Urdu-script word using productive affixes
    (prefixes, suffixes, and regular plural inflection markers) into known roots.
    Returns Roman Urdu string if resolved, or None.
    """
    # 1. Productive Prefixes (e.g. بےوقوف -> bewaqoof, ناممکن -> namumkin, بدقسمتی -> badqismati)
    for pfx, roman_pfx in PREFIXES:
        pfx_nfc = _nfc(pfx)
        if word_nfc.startswith(pfx_nfc) and len(word_nfc) > len(pfx_nfc) + 1:
            root = word_nfc[len(pfx_nfc):]
            if root in _DICT_NFC:
                return roman_pfx + _DICT_NFC[root]

    # 2. Productive Suffixes (e.g. سمجھدار -> samajhdar, ضرورتمند -> zarooratmand, امیدوار -> umeedwar)
    for sfx, roman_sfx in SUFFIXES:
        sfx_nfc = _nfc(sfx)
        if word_nfc.endswith(sfx_nfc) and len(word_nfc) > len(sfx_nfc) + 1:
            root = word_nfc[:-len(sfx_nfc)]
            if root in _DICT_NFC:
                return _DICT_NFC[root] + roman_sfx

    # 3. Regular Plural Inflections:
    # 3a. -وں (-on) plural: e.g. کتابوں -> kitabon, دکانوں -> dukanon
    if word_nfc.endswith(_nfc('وں')) and len(word_nfc) > 3:
        stem = word_nfc[:-2]
        if stem in _DICT_NFC:
            return _DICT_NFC[stem] + 'on'
        if (stem + _nfc('ہ')) in _DICT_NFC:
            r = _DICT_NFC[stem + _nfc('ہ')]
            return (r[:-1] if r.endswith(('a', 'e')) else r) + 'on'
        if (stem + _nfc('ا')) in _DICT_NFC:
            r = _DICT_NFC[stem + _nfc('ا')]
            return (r[:-1] if r.endswith(('a', 'e')) else r) + 'on'

    # 3b. -یں (-ein) plural: e.g. کتابیں -> kitabein, باتیں -> batein
    if word_nfc.endswith(_nfc('یں')) and len(word_nfc) > 3:
        stem = word_nfc[:-2]
        if stem in _DICT_NFC:
            return _DICT_NFC[stem] + 'ein'
        if (stem + _nfc('ی')) in _DICT_NFC:
            return _DICT_NFC[stem + _nfc('ی')] + 'an'

    # 3c. -ات (-aat) Arabic plural: e.g. معلومات -> maloomat, احساسات -> ehsasaat
    if word_nfc.endswith(_nfc('ات')) and len(word_nfc) > 3:
        stem = word_nfc[:-2]
        if stem in _DICT_NFC:
            return _DICT_NFC[stem] + 'aat'
        if (stem + _nfc('ہ')) in _DICT_NFC:
            r = _DICT_NFC[stem + _nfc('ہ')]
            return (r[:-1] if r.endswith(('a', 'e')) else r) + 'aat'

    # 3d. -یاں (-iyan) plural for feminine nouns ending in 'ی': e.g. گاڑیاں -> gaadiyan
    if word_nfc.endswith(_nfc('یاں')) and len(word_nfc) > 3:
        stem = word_nfc[:-3]
        if (stem + _nfc('ی')) in _DICT_NFC:
            return _DICT_NFC[stem + _nfc('ی')] + 'an'

    return None

# Punctuation characters including Urdu punctuation
_PUNCT_CHARS = r',.:;?!،۔؛؟\-–—\(\)\[\]"\'«»'
_PUNCT_RE = re.compile(rf'^([{_PUNCT_CHARS}]*)(.*?)([{_PUNCT_CHARS}]*)$')


def _convert_urdu_punct(s: str) -> str:
    """Converts Urdu punctuation to Latin punctuation for Roman text."""
    return s.replace('۔', '.').replace('،', ',').replace('؟', '?').replace('؛', ';')


def transliterate_word(token: str) -> str:
    """
    Transliterate a single token.
    Leading/trailing punctuation is preserved (Urdu punctuation mapped to Latin).
    Latin-script words (English) are returned as-is.
    4-Tier resolution:
      1. User Preferences & Expanded Dictionary
      2. Morphological Affix Engine
      3. Neural Transliteration Fallback (IndicXlit)
      4. Position-aware Character Map
    """
    if not token:
        return token

    # Strip punctuation wrapper
    m = _PUNCT_RE.match(token)
    if m and m.group(2):
        pre, core, post = _convert_urdu_punct(m.group(1)), m.group(2), _convert_urdu_punct(m.group(3))
    else:
        pre, core, post = '', token, ''

    # Latin-only core → English word, pass through with converted punctuation
    if not _has_urdu(core):
        return pre + core + post

    # 1. Dictionary lookup — NFC-normalise the core before matching
    core_nfc = _nfc(core.strip())
    if core_nfc in _DICT_NFC:
        return pre + _DICT_NFC[core_nfc] + post

    # 2. Morphological Affix Engine (prefixes, suffixes, plurals)
    affix_resolved = _morphological_decompose(core_nfc)
    if affix_resolved is not None:
        return pre + affix_resolved + post

    # 3. Neural Transliteration Fallback (AI4Bharat IndicXlit if available)
    neural_resolved = _neural_transliterate(core_nfc)
    if neural_resolved is not None:
        return pre + neural_resolved + post

    # 4. Deterministic Character-level fallback (also NFC-normalises internally)
    return pre + _char_map_word(core) + post


# ── Abbreviation collapsing ───────────────────────────────────────────────
# When consecutive tokens are each a single uppercase letter (A, F, M …),
# collapse "A F M" → "AFM" — common for spoken abbreviations in Urdu.
_ABBREV_RE = re.compile(r'\b([A-Z])((?:\s+[A-Z])+)\b')


# ── Full-text transliteration ─────────────────────────────────────────────

# Split on whitespace, keeping the separators so we can rejoin exactly.
_SPLIT_RE = re.compile(r'(\s+)')


def transliterate(text: str) -> str:
    """
    Convert a mixed Urdu-script / Latin-script string to Roman Urdu.
    Whitespace and punctuation layout are preserved exactly.
    English words (already Latin script) are left unchanged.
    Consecutive single-letter uppercase tokens (A F M) are joined as AFM.
    """
    parts = _SPLIT_RE.split(text)   # alternates: [word, space, word, space, ...]
    roman = ''.join(
        p if _SPLIT_RE.match(p) else transliterate_word(p)
        for p in parts
    )
    # Collapse "A F M" → "AFM"
    roman = _ABBREV_RE.sub(lambda m: m.group(1) + m.group(2).replace(' ', ''), roman)
    return roman


# ── SRT helper ────────────────────────────────────────────────────────────

def transliterate_srt(srt_text: str) -> str:
    """
    Transliterate only the subtitle lines in an SRT file.
    Index lines (digits) and timestamp lines (-->)  are left untouched.
    """
    lines = srt_text.splitlines(keepends=True)
    out = []
    for line in lines:
        stripped = line.strip()
        # Index line (just a number)
        if stripped.isdigit():
            out.append(line)
        # Timestamp line
        elif '-->' in stripped:
            out.append(line)
        # Empty line (SRT block separator)
        elif stripped == '':
            out.append(line)
        # Subtitle text line
        else:
            out.append(transliterate(stripped) + '\n')
    return ''.join(out)


# ── Quick smoke-test ──────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    samples = [
        'اسلام علیکم dear students, I have some exciting news to share with you.',
        'ہم نے exam hack sessions کروایا تھے جو آپ لوگوں نے بہت ہی appreciate کیا تھا.',
        'آپ لوگوں کی extreme request کی بیٹ کی اوپر ہم اس میں مزید papers add کر رہے ہیں.',
        'ایڈوانس فائننشل مینجمنٹ پہ بھی ایگزام ہیک سیشنز کروائیں گے',
        'ایگزام ٹیکسٹ پہ بات ہوگی ٹیکنیک پہ بات ہوگی',
        'اے ایف ایم میں تو پروفیشنل مارکس بھی ہیں',
        'تو آئی ہوپ تو جوائن یو آل this session.',
    ]

    print('=== Roman Urdu smoke-test ===\n')
    for s in samples:
        print('IN :', s)
        print('OUT:', transliterate(s))
        print()

    print('=== Active spelling preferences ===')
    if SPELLING_PREFS:
        for k, v in SPELLING_PREFS.items():
            print(f'  {k}  →  {v}')
    else:
        print('  (none — using defaults from DICTIONARY)')
        print('  Edit SPELLING_PREFS at the top of roman_urdu.py to customise.')
