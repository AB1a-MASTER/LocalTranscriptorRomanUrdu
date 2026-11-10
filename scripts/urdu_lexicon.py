"""
urdu_lexicon.py
===============
Comprehensive Roman Urdu lexicon & morphological decomposition rules.
Designed for authentic Pakistani Roman Urdu transliteration.
"""

# ── Morphological Affixes (Prefixes & Suffixes) ───────────────────────────

PREFIXES: list[tuple[str, str]] = [
    # (Urdu Prefix, Roman Prefix)
    ('بے', 'be'),        # بےوقوف -> bewaqoof, بےشمار -> beshumar
    ('نا', 'na'),        # ناممکن -> namumkin, نااہل -> na-ahal
    ('بد', 'bad'),       # بدقسمت -> badqismat, بدتمیز -> badtameez
    ('غیر', 'ghair '),   # غیرقانونی -> ghair qanooni
    ('با', 'ba-'),       # باعزت -> ba-izzat, بااختیار -> ba-ikhtiyar
    ('ہم', 'ham'),       # ہمدرد -> hamdard, ہمسفر -> hamsafar
    ('خود', 'khud '),    # خودمختار -> khud mukhtaar
    ('کم', 'kam '),      # کمزور -> kamzor, کم عقل -> kam aql
    ('خوش', 'khush '),   # خوش آمدید -> khush aamdeed, خوشحال -> khushhaal
    ('لا', 'la-'),       # لاعلاج -> la-ilaaj, لاوارث -> la-waaris
    ('اہل', 'ahl-e-'),   # اہل قلم -> ahl-e-qalam
]

SUFFIXES: list[tuple[str, str]] = [
    # (Urdu Suffix, Roman Suffix)
    ('ترین', 'tareen'),       # بہترین -> behtareen, بدترین -> badtareen
    ('دار', 'dar'),           # سمجھدار -> samajhdar, شاندار -> shandar
    ('مند', 'mand'),          # ضرورتمند -> zarooratmand, عقلمند -> aqlmand
    ('وار', 'war'),           # امیدوار -> umeedwar, سوگوار -> sogwar
    ('ساز', 'saaz'),          # کارساز -> karsaaz, دستانہ ساز -> dastana saaz
    ('دان', 'daan'),          # قلمدان -> qalamdaan, سائنسدان -> sciencedaan
    ('ستان', 'stan'),         # پاکستان -> pakistan, گلستان -> gulistan
    ('پذیر', 'pazeer'),       # ترقی پذیر -> taraqqi pazeer
    ('پسند', 'pasand'),       # امن پسند -> aman pasand
    ('خانہ', 'khana'),        # شفاخانہ -> shafakhana, کارخانہ -> karkhana
    ('کار', 'kaar'),          # فنکار -> fankaar, اداکار -> adakaar
    ('شناس', 'shanaas'),      # مردم شناس -> mardum shanaas
    ('آموز', 'aamoz'),        # سبق آموز -> sabaq aamoz
    ('انگیز', 'angeez'),      # حیرت انگیز -> hairat angeez
    ('پرست', 'parast'),       # خود پرست -> khud parast
    ('طلب', 'talab'),         # راحت طلب -> rahat talab
    ('نما', 'numa'),          # رہنما -> rehnuma
]

# ── Comprehensive Lexicon Dictionary (Curated Pakistani Roman Urdu) ────────

URDU_LEXICON: dict[str, str] = {
    # ── High-frequency Short-Vowel Nouns & Concepts ────────────────────────
    'بہتر': 'behtar',          'بہترین': 'behtareen',       'بدترین': 'badtareen',
    'شروع': 'shuroo',          'شروعات': 'shurooat',        'اسکیم': 'scheme',
    'بچت': 'bachat',           'بچتیں': 'bachatein',        'بچتوں': 'bachaton',
    'ترقی': 'taraqqi',         'ترقیاتی': 'taraqqiyati',
    'حکومت': 'hukoomat',       'حکومتی': 'hukoomati',      'حکومتوں': 'hukoomaton',
    'سمجھ': 'samajh',          'سمجھنا': 'samajhna',        'سمجھانا': 'samjhana',
    'دفتر': 'daftar',          'دفتری': 'daftari',          'دفاتر': 'dafaatir',
    'سبق': 'sabaq',            'سبقیں': 'sabaqein',         'اسباق': 'asbaaq',
    'خبر': 'khabar',           'خبریں': 'khabrein',         'خبروں': 'khabron',
    'نظر': 'nazar',            'نظریں': 'nazrein',          'نظریہ': 'nazriya',
    'شہر': 'shehar',           'شہری': 'shehri',            'شہروں': 'shehron',
    'ملک': 'mulk',             'ملکی': 'mulki',             'ممالک': 'mamalik',
    'مسئلہ': 'masla',          'مسائل': 'masayil',          'مسئلوں': 'maslon',
    'معلومات': 'maloomat',     'معلوم': 'maloom',
    'تجربہ': 'tajurba',        'تجربات': 'tajurbaat',       'تجربہ کار': 'tajurbakaar',
    'ضرورت': 'zaroorat',       'ضروریات': 'zarooriyat',
    'قدر': 'qadr',             'قدرتی': 'qudrati',
    'قسم': 'qism',             'اقسام': 'aqsaam',           'قسمیں': 'qismein',
    'طرف': 'taraf',            'اطراف': 'atraaf',
    'وجہ': 'wajah',            'وجوہات': 'wajoohaat',
    'طریقہ': 'tareeqa',        'طریقے': 'tareeqay',         'طریقوں': 'tareeqon',
    'فیصلہ': 'faisla',         'فیصلے': 'faislay',          'فیصلوں': 'faislon',
    'رابطہ': 'raabta',         'رابطے': 'raabtay',          'رابطوں': 'raabton',
    'فاصلہ': 'faasla',         'فاصلے': 'faaslay',          'فاصلوں': 'faaslon',
    'حاصل': 'haasil',          'حصول': 'husool',
    'شامل': 'shaamil',         'شمولیت': 'shamooliyat',
    'کوشش': 'koshish',         'کوششیں': 'koshishein',      'کوششوں': 'koshishon',
    'خواہش': 'khwahish',       'خواہشات': 'khwahishaat',    'خواہشیں': 'khwahishein',
    'زندگی': 'zindagi',        'زندہ': 'zinda',
    'محبت': 'mohabbat',        'نفرت': 'nafrat',
    'عزت': 'izzat',            'ذلت': 'zillat',
    'محنت': 'mehnat',          'مشقت': 'mushaqqat',
    'قسمت': 'qismat',
    'حقیقت': 'haqeeqat',       'حقیقی': 'haqeeqi',          'حقائق': 'haqayiq',
    'طاقت': 'taaqat',          'طاقتور': 'taaqatwar',
    'کمزور': 'kamzor',         'کمزوری': 'kamzori',
    'صحت': 'sehat',            'بیمار': 'beemar',           'بیماری': 'beemari',
    'تعلیم': 'taleem',         'تعلیمی': 'taleemi',
    'تربیت': 'tarbiyat',       'استاد': 'ustad',            'اساتذہ': 'asatza',
    'طالب': 'talib',           'طلبہ': 'talba',             'طالبات': 'talibaat',
    'طالب علم': 'talib-e-ilm',
    'موقع': 'mouqa',           'مواقع': 'mawaqay',
    'معاملہ': 'mamla',         'معاملات': 'mamlaat',
    'دنیا': 'dunya',           'جہان': 'jahan',
    'عوام': 'awaam',           'خواص': 'khawaas',
    'قانون': 'qanoon',         'قانونی': 'qanooni',         'قوانین': 'qawaneen',
    'عدالت': 'adaalat',        'عدالتیں': 'adaalatein',     'انصاف': 'insaaf',
    'معاشرہ': 'muashra',       'معاشی': 'maashi',           'معیشت': 'maeeshat',
    'کاروبار': 'karobar',      'کاروباری': 'karobari',
    'تجارت': 'tijaarat',       'صنعت': 'san\'at',           'صنعتی': 'san\'ati',
    'ملازمت': 'mulazmat',      'نوکری': 'naukri',           'نوکریاں': 'naukriyan',
    'تنخواہ': 'tankhwah',      'آمدن': 'aamdan',            'آمدنی': 'aamdani',
    'خرچہ': 'kharcha',         'خرچ': 'kharch',             'اخراجات': 'akhrajaat',
    'قیمت': 'qeemat',          'قیمتیں': 'qeematein',       'قیمتی': 'qeemti',
    'دکان': 'dukaan',          'دکانیں': 'dukaanein',       'دکاندار': 'dukaandar',
    'خریداری': 'khareedari',   'خرید': 'khareed',           'فروخت': 'farokht',
    'نقصان': 'nuqsaan',        'نقصانات': 'nuqsanaat',      'فائدہ': 'faida',            'فوائد': 'fawayid',
    'کامیابی': 'kamyabi',      'کامیاب': 'kamyab',          'ناکامی': 'nakami',
    'امید': 'umeed',           'امیدیں': 'umeedein',        'مایوسی': 'mayoosi',
    'خوشی': 'khushi',          'خوشیاں': 'khushiyan',       'غم': 'gham',                'پریشانی': 'pareshani',
    'عقل': 'aql',              'عقلمندی': 'aqlmandi',
    'دل': 'dil',               'دماغ': 'dimagh',            'دھڑکن': 'dhadkan',
    'آنکھ': 'aankh',           'آنکھیں': 'aankhein',        'آنکھوں': 'aankhon',
    'کان': 'kaan',             'ناک': 'naak',               'منہ': 'munh',
    'ہاتھ': 'haath',           'پاؤں': 'paon',              'پیر': 'pair',
    'جسم': 'jism',             'سر': 'sar',                 'بال': 'baal',
    'خون': 'khoon',            'پسینہ': 'paseena',

    # ── Time, Calendar & Nature ───────────────────────────────────────────
    'صبح': 'subah',            'شام': 'shaam',              'دوپہر': 'dopehar',
    'رات': 'raat',             'راتیں': 'ratein',           'راتوں': 'raton',
    'کل': 'kal',               'پرسوں': 'parson',           'آج': 'aaj',
    'ہفتہ': 'hafta',           'ہفتے': 'haftay',            'ہفتوں': 'hafton',
    'مہینہ': 'maheena',        'مہینے': 'maheenay',         'مہینوں': 'maheenon',
    'سال': 'saal',             'سالانہ': 'saalana',         'سالوں': 'saalon',
    'سردی': 'sardi',           'گرمی': 'garmi',             'بہار': 'bahaar',            'خزاں': 'khizaan',
    'بارش': 'baarish',         'بارشیں': 'baarishein',      'دھوپ': 'dhoop',
    'ہوا': 'hawa',             'ہوائیں': 'hawayein',        'بادل': 'baadal',
    'آسمان': 'aasman',         'زمین': 'zameen',            'ستارے': 'sitaare',          'چاند': 'chaand',            'سورج': 'sooraj',
    'پہاڑ': 'pahaar',          'دریا': 'darya',             'سمندر': 'samandar',         'جنگل': 'jungle',

    # ── Transport, Movement & Urban Life ──────────────────────────────────
    'راستہ': 'raasta',         'راستے': 'raastay',          'راستوں': 'raaston',
    'سڑک': 'sarak',            'سڑکیں': 'sadrqein',         'گلی': 'gali',               'گلیاں': 'galiyan',
    'گاڑی': 'gaadi',           'گاڑیاں': 'gaadiyan',        'موٹرسائیکل': 'motorcycle',
    'جہاز': 'jahaz',           'ٹرین': 'train',             'بس': 'bus',
    'سفر': 'safar',            'مسافر': 'musafir',          'منزل': 'manzil',
    'سٹیشن': 'station',        'ائرپورٹ': 'airport',        'اسٹاپ': 'stop',

    # ── Family & Human Relations ──────────────────────────────────────────
    'والد': 'walid',           'والدہ': 'walida',           'والدین': 'walidain',
    'باپ': 'baap',             'ماں': 'maan',               'امی': 'ammi',               'ابو': 'abbu',
    'بھائی': 'bhai',           'بہن': 'behan',              'بہنیں': 'behnein',
    'بیٹا': 'beta',            'بیٹے': 'betay',             'بیٹی': 'beti',              'بیٹیاں': 'betiyan',
    'بچہ': 'bachcha',          'بچے': 'bachche',            'بچی': 'bachchi',            'بچوں': 'bachchon',
    'دوست': 'dost',            'دوستی': 'dosti',            'دوستوں': 'doston',
    'دشمن': 'dushman',         'دشمنی': 'dushmani',
    'ہمسایہ': 'hamsaya',       'پڑوسی': 'parosi',
    'رشتہ': 'rishta',          'رشتے': 'rishtay',           'رشتہ دار': 'rishtedar',

    # ── Food, Sustenance & Home ───────────────────────────────────────────
    'کھانا': 'khana',          'پینا': 'peena',             'پانی': 'paani',
    'روٹی': 'roti',            'چاول': 'chawal',            'چائے': 'chai',
    'دودھ': 'doodh',           'چینی': 'cheeni',            'نمک': 'namak',
    'گوشت': 'gosht',           'سبزی': 'sabzi',             'پھل': 'phal',
    'میٹھا': 'meetha',         'نمکین': 'namkeen',
    'کچن': 'kitchen',          'باورچی خانہ': 'bawarchikhana',
    'کمرہ': 'kamra',           'کمرے': 'kamray',            'کمروں': 'kamron',
    'دروازہ': 'darwaza',       'دروازے': 'darwazay',        'کھڑکی': 'khirki',           'چھت': 'chhat',

    # ── Additional Common Verbs & Participles ─────────────────────────────
    'بولنا': 'bolna',          'بولا': 'bola',              'بولی': 'boli',              'بولے': 'bolay',
    'کہنا': 'kehna',           'کہا': 'kaha',               'کہہ': 'keh',                'کہتے': 'kehte',
    'پوچھنا': 'poochna',       'پوچھا': 'poocha',           'پوچھیں': 'poochein',
    'مانگنا': 'maangna',       'مانگا': 'maanga',
    'چھوڑنا': 'chhorna',       'چھوڑا': 'chhora',           'چھوڑیں': 'chhorein',
    'پکڑنا': 'pakarna',        'پکڑا': 'pakra',
    'گرنا': 'girna',           'گرایا': 'giraya',
    'اٹھنا': 'uthna',          'اٹھایا': 'uthaya',          'اٹھیں': 'uthein',
    'بیٹھنا': 'bethna',        'بیٹھا': 'betha',            'بیٹھیں': 'bethein',
    'چلنا': 'chalna',          'چلا': 'chala',              'چلی': 'chali',              'چلے': 'chalay',
    'روکنا': 'rokna',          'روکا': 'roka',              'روکیں': 'rokein',
    'سوچنا': 'sochna',         'سوچا': 'socha',             'سوچیں': 'sochein',
    'ڈھونڈنا': 'dhoondna',     'ڈھونڈا': 'dhoonda',
    'بھیجنا': 'bhejna',        'بھیجا': 'bhejha',           'بھیجیں': 'bhejein',
    'لانا': 'laana',           'لایا': 'laya',              'لائی': 'layi',              'لائے': 'laaye',
    'لے جانا': 'le jaana',
    'ماننا': 'manna',          'مانا': 'maana',
    'جیتنا': 'jeetna',         'جیتا': 'jeeta',
    'ہارنا': 'haarna',         'ہارا': 'haara',
    'بچنا': 'bachna',          'بچایا': 'bachaya',
    'مرنا': 'marna',           'مارنا': 'maarna',           'مارا': 'maara',
    'سونا': 'sona',            'جاگنا': 'jaagna',           'جاگا': 'jaaga',
    'ہنسنا': 'hansna',         'ہنسا': 'hansa',
    'رونا': 'rona',            'رویا': 'roya',
    'تھکنا': 'thakna',         'تھکا': 'thaka',             'تھکن': 'thakan',
    'ڈرنا': 'darna',           'ڈر': 'dar',                 'خوف': 'khauf',

    # ── Conversational Particles & Expressions ─────────────────────────────
    'بالکل': 'bilkul',         'یقیناً': 'yaqeenan',        'یقین': 'yaqeen',
    'ضرور': 'zaroor',          'شاید': 'shayad',            'امید ہے': 'umeed hai',
    'خیر': 'khair',            'خیریت': 'khairiyat',        'شکر': 'shukr',              'شکریہ': 'shukriya',
    'مہربانی': 'meherbani',    'معذرت': 'maazrat',          'معاف': 'maaf',
    'براہ کرم': 'barah-e-karam',
    'انشاءاللہ': 'inshallah',  'ماشاءاللہ': 'mashallah',    'الحمدللہ': 'alhamdulillah', 'سبحان اللہ': 'subhanallah',
    'خدا حافظ': 'khuda hafiz', 'اللہ حافظ': 'allah hafiz',
    'جناب': 'janaab',          'صاحب': 'sahab',             'محترم': 'mohtaram',         'محترمہ': 'mohtarma',

    # ── Numbers 1 to 30 & Units ───────────────────────────────────────────
    'گیارہ': 'gyarah',         'بارہ': 'barah',             'تیرہ': 'terah',             'چودہ': 'chaudah',
    'پندرہ': 'pandrah',        'سولہ': 'solah',             'سترہ': 'satrah',            'اٹھارہ': 'atharah',
    'انیس': 'unnees',          'بیس': 'bees',               'اکیس': 'ikkees',            'بائیس': 'baees',
    'تئیس': 'teyees',          'چوبیس': 'chaubees',         'پچیس': 'pachees',           'چھبیس': 'chhabees',
    'ستائیس': 'sataees',       'اٹھائیس': 'athaees',        'انتیس': 'untees',           'تیس': 'tees',
    'چالیس': 'chalees',        'پچاس': 'pachaas',           'ساٹھ': 'saath',             'ستر': 'sattar',
    'اسی': 'assi',             'نوے': 'navway',             'سو': 'sau',                 'ہزار': 'hazaar',
    'لاکھ': 'laakh',           'کروڑ': 'karor',             'ارب': 'arab',

    # ── Technology, Computing & Internet Loanwords in Urdu Script ──────────
    'کمپیوٹر': 'computer',     'سافٹ ویئر': 'software',     'ہارڈ ویئر': 'hardware',
    'انٹرنیٹ': 'internet',     'ویب سائٹ': 'website',       'ایپلیکیشن': 'application',   'ایپ': 'app',
    'موبائل': 'mobile',        'فون': 'phone',              'اسمارٹ فون': 'smartphone',
    'نیٹ ورک': 'network',      'سرور': 'server',            'ڈیٹا بیس': 'database',
    'پروگرامنگ': 'programming','ڈویلپر': 'developer',       'ڈیزائنر': 'designer',
    'کوڈنگ': 'coding',         'سورس کوڈ': 'source code',
    'فائل': 'file',            'فائلیں': 'files',           'فولڈر': 'folder',           'ڈرائیو': 'drive',
    'اسکرین': 'screen',        'ڈسپلے': 'display',          'کی بورڈ': 'keyboard',       'ماؤس': 'mouse',
    'مائیک': 'mic',            'ہیڈ فون': 'headphone',      'اسپیکر': 'speaker',
    'کیمرہ': 'camera',         'تصویر': 'tasweer',          'تصاویر': 'tasweerein',
    'ڈاؤن لوڈ': 'download',    'اپ لوڈ': 'upload',          'انسٹال': 'install',
    'سیٹنگز': 'settings',      'سیٹنگ': 'setting',          'کنفیگریشن': 'configuration',
    'پاس ورڈ': 'password',     'لاگ ان': 'login',           'سائن اپ': 'signup',

    # ── Academia, Professional & Office Life ───────────────────────────────
    'اسکول': 'school',         'کالج': 'college',           'یونیورسٹی': 'university',
    'کیمپس': 'campus',         'ڈگری': 'degree',            'ڈپلومہ': 'diploma',         'سرٹیفکیٹ': 'certificate',
    'کورس': 'course',          'کورسز': 'courses',          'سلیبس': 'syllabus',
    'لیکچر': 'lecture',        'لیکچرز': 'lectures',
    'ایڈمیشن': 'admission',    'فیس': 'fees',               'سکالرشپ': 'scholarship',
    'لائبریری': 'library',     'کتاب': 'kitab',             'کتابیں': 'kitabein',        'کتابوں': 'kitabon',
    'قلم': 'qalam',            'کاپی': 'copy',              'ڈائری': 'diary',
    'نوٹ بک': 'notebook',      'صفحہ': 'safha',             'صفحات': 'safhaat',

    # ── Banking, Finance & Corporate (ACCA / CA / Business) ───────────────
    'بینک': 'bank',            'بینکنگ': 'banking',         'بینکر': 'banker',
    'کریڈٹ': 'credit',         'ڈیبٹ': 'debit',             'لون': 'loan',
    'انوائس': 'invoice',       'انوائسز': 'invoices',       'بل': 'bill',                'بلنگ': 'billing',
    'پیمنٹ': 'payment',        'پیمنٹس': 'payments',        'ٹرانزیکشن': 'transaction',  'ٹرانزیکشنز': 'transactions',
    'اسٹیٹمنٹ': 'statement',   'اکاؤنٹس': 'accounts',
    'بجٹ': 'budget',           'بجٹنگ': 'budgeting',
    'آڈٹنگ': 'auditing',       'واؤچر': 'voucher',          'لیجر': 'ledger',
    'مارکیٹنگ': 'marketing',   'سیلز': 'sales',             'کسٹمر': 'customer',         'کلائنٹ': 'client',
    'کمپنی': 'company',        'کمپنیاں': 'companies',     'ادارہ': 'idara',            'ادارے': 'idaray',           'اداروں': 'idaron',
    'مینیجر': 'manager',       'ڈائریکٹر': 'director',      'سی ای او': 'CEO',           'میٹنگ': 'meeting',
}
