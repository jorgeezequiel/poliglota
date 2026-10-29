#!/usr/bin/env python3
"""
Phase B — Language/Model Compatibility Audit

Investigates the compatibility between QuestLog locales and the NLLB model.
Verifies locale codes, language codes, and expected model support.
"""

from __future__ import annotations

import json
from pathlib import Path


# NLLB-200 supported languages (ISO 639-3 codes as required by model)
# The model uses ISO 639-3 instead of ISO 639-1
NLLB_SUPPORTED_LANGUAGES = {
    # Format: iso_639_3_code -> (language_name, common_variants)
    "eng": ("English", ["en_US", "en_GB", "en_AU", "en_CA", "en_NZ", "en_IE", "en_IN"]),
    "por": ("Portuguese", ["pt_BR", "pt_PT"]),
    "spa": ("Spanish", ["es_ES", "es_MX", "es_AR"]),
    "fra": ("French", ["fr_FR", "fr_CA", "fr_BE"]),
    "deu": ("German", ["de_DE", "de_AT", "de_CH"]),
    "ita": ("Italian", ["it_IT"]),
    "nld": ("Dutch", ["nl_NL", "nl_BE"]),
    "rus": ("Russian", ["ru_RU"]),
    "pla": ("Polish", ["pl_PL"]),
    "ces": ("Czech", ["cs_CZ"]),
    "slk": ("Slovak", ["sk_SK"]),
    "ron": ("Romanian", ["ro_RO"]),
    "ell": ("Greek", ["el_GR"]),
    "hrv": ("Croatian", ["hr_HR"]),
    "slv": ("Slovenian", ["sl_SI"]),
    "hun": ("Hungarian", ["hu_HU"]),
    "kok": ("Konkani", ["kok_IN"]),
    "san": ("Sanskrit", ["san_IN"]),
    "urd": ("Urdu", ["ur_PK", "ur_IN"]),
    "ben": ("Bengali", ["bn_BD", "bn_IN"]),
    "hin": ("Hindi", ["hi_IN"]),
    "mar": ("Marathi", ["mr_IN"]),
    "pan": ("Punjabi", ["pa_IN", "pa_PK"]),
    "tam": ("Tamil", ["ta_IN"]),
    "tel": ("Telugu", ["te_IN"]),
    "kan": ("Kannada", ["kn_IN"]),
    "mal": ("Malayalam", ["ml_IN"]),
    "ory": ("Odia", ["or_IN"]),
    "guj": ("Gujarati", ["gu_IN"]),
    "jav": ("Javanese", ["id_ID"]),  # Note: Javanese differs from Indonesian
    "ind": ("Indonesian", ["id_ID"]),
    "msa": ("Malay", ["ms_MY"]),
    "vie": ("Vietnamese", ["vi_VN"]),
    "tha": ("Thai", ["th_TH"]),
    "lao": ("Lao", ["lo_LA"]),
    "khm": ("Khmer", ["km_KH"]),
    "mya": ("Burmese", ["my_MM"]),
    "jpn": ("Japanese", ["ja_JP"]),
    "kor": ("Korean", ["ko_KR"]),
    "zho_Hans": ("Chinese Simplified", ["zh_CN", "zh_SG"]),
    "zho_Hant": ("Chinese Traditional", ["zh_TW", "zh_HK", "zh_MO"]),
    "fin": ("Finnish", ["fi_FI"]),
    "swe": ("Swedish", ["sv_SE"]),
    "nor": ("Norwegian", ["nb_NO"]),
    "dan": ("Danish", ["da_DK"]),
    "isl": ("Icelandic", ["is_IS"]),
    "ukr": ("Ukrainian", ["uk_UA"]),
    "bul": ("Bulgarian", ["bg_BG"]),
    "srp_Latn": ("Serbian (Latin)", ["sr_RS"]),
    "srp_Cyrl": ("Serbian (Cyrillic)", ["sr_RS"]),
    "mkd": ("Macedonian", ["mk_MK"]),
    "als": ("Albanian", ["sq_AL"]),
    "est": ("Estonian", ["et_EE"]),
    "lav": ("Latvian", ["lv_LV"]),
    "lit": ("Lithuanian", ["lt_LT"]),
    "tur": ("Turkish", ["tr_TR"]),
    "kat": ("Georgian", ["ka_GE"]),
    "hye": ("Armenian", ["hy_AM"]),
    "kaz": ("Kazakh", ["kk_KZ"]),
    "uzn": ("Uzbek", ["uz_UZ"]),
    "ara": ("Arabic", ["ar_SA", "ar_AE", "ar_EG", "ar_MA"]),  # Generic Arabic
    "heb": ("Hebrew", ["he_IL"]),
    "fas": ("Farsi/Persian", ["fa_IR"]),
    "sin": ("Sinhala", ["si_LK"]),
    "nep": ("Nepali", ["ne_NP"]),
    "fil": ("Filipino", ["fil_PH"]),
    "mlt": ("Maltese", ["mt_MT"]),
    "afr": ("Afrikaans", ["af_ZA"]),
    "eng_Dsrt": ("English Deseret", ["en_US"]),  # Variant/transliteration
}

# Additional language codes in NLLB that might have limited coverage
NLLB_ADDITIONAL_LANGS = {
    "acm": "Iraqi Arabic",
    "aeb": "Tunisian Arabic",
    "afr": "Afrikaans",
    "ajp": "South Levantine Arabic",
    "aka": "Akan",
    "amh": "Amharic",
    "apc": "North Levantine Arabic",
    "arb": "Standard Arabic",
    "ars": "Najdi Arabic",
    "ary": "Moroccan Arabic",
    "asm": "Assamese",
    "ast": "Asturian",
    "awa": "Awadhi",
    "ayl": "Aymara",
    "azb": "South Azerbaijani",
    "azj": "North Azerbaijani",
    "bak": "Bashkir",
    "bam": "Bambara",
    "ban": "Balinese",
    "bas": "Basaa",
    "bel": "Belarusian",
    "bem": "Bemba",
    "ben": "Bengali",
    "bho": "Bhojpuri",
    "bjn": "Banjar",
    "bod": "Tibetan",
    "bos": "Bosnian",
    "bug": "Buginese",
    "bul": "Bulgarian",
    "cat": "Catalan",
    "ceb": "Cebuano",
    "ces": "Czech",
    "cjk": "Chokwe",
    "ckb": "Central Kurdish",
    "crh": "Crimean Tatar",
    "cym": "Welsh",
    "dan": "Danish",
    "deu": "German",
    "dik": "Southwestern Dinka",
    "dyu": "Dyula",
    "ell": "Greek",
    "eng": "English",
    "enm": "Middle English",
    "epo": "Esperanto",
    "est": "Estonian",
    "eus": "Basque",
    "ewe": "Ewe",
    "fao": "Faroese",
    "fij": "Fijian",
    "fin": "Finnish",
    "fon": "Fon",
    "fra": "French",
    "fur": "Friulian",
    "fuv": "Nigerian Fulfulde",
    "gaz": "Oromo",
    "gla": "Scottish Gaelic",
    "gle": "Irish Gaelic",
    "glg": "Galician",
    "grn": "Guarani",
    "guj": "Gujarati",
    "gun": "Gun",
    "guz": "Gusii",
    "hak": "Hakka Chinese",
    "han": "Han (generic)",
    "hau": "Hausa",
    "heb": "Hebrew",
    "hin": "Hindi",
    "hne": "Chhattisgarhi",
    "hrv": "Croatian",
    "hun": "Hungarian",
    "hye": "Armenian",
    "iba": "Iban",
    "ibb": "Ibibio",
    "ind": "Indonesian",
    "isl": "Icelandic",
    "ita": "Italian",
    "jav": "Javanese",
    "jpn": "Japanese",
    "kab": "Kabyle",
    "kac": "Kachin",
    "kam": "Kamba",
    "kan": "Kannada",
    "kas": "Kashmiri",
    "kat": "Georgian",
    "kaz": "Kazakh",
    "kbp": "Kabiyè",
    "kea": "Kabuverdianu",
    "khm": "Khmer",
    "kik": "Kikuyu",
    "kin": "Kinyarwanda",
    "kir": "Kirghiz",
    "kmb": "Kimbundu",
    "kmr": "Kurmanji Kurdish",
    "knc": "Central Kurdish",
    "kod": "Kodi",
    "kok": "Konkani",
    "kon": "Kikongo",
    "kor": "Korean",
    "lad": "Ladino",
    "lag": "Langi",
    "lao": "Lao",
    "lav": "Latvian",
    "lbx": "Ligurian",
    "lgg": "Luganda",
    "lij": "Ligurian",
    "lin": "Lingala",
    "lit": "Lithuanian",
    "lmo": "Lombard",
    "ltg": "Latgalian",
    "ltz": "Luxembourgish",
    "lua": "Luba-Kasai",
    "luo": "Luo",
    "lus": "Mizo",
    "luy": "Luyia",
    "mac": "Macedonian",
    "mai": "Maithili",
    "mal": "Malayalam",
    "mar": "Marathi",
    "min": "Minangkabau",
    "mkd": "Macedonian",
    "plt": "Plateau Malagasy",
    "moh": "Mohawk",
    "mpl": "Mapudungun",
    "mri": "Maori",
    "msa": "Malay",
    "msl": "Malay (generic)",
    "mya": "Burmese",
    "nld": "Dutch",
    "nno": "Norwegian Nynorsk",
    "nob": "Norwegian Bokmal",
    "npi": "Nepali",
    "nso": "Northern Sotho",
    "nld": "Dutch",
    "nya": "Chinyanja",
    "oci": "Occitan",
    "ory": "Odia",
    "pag": "Pangasinan",
    "pan": "Punjabi",
    "pap": "Papiamento",
    "pbt": "Southern Pashto",
    "pdu": "Pomo",
    "pes": "Dari Persian",
    "pht": "Pattani Malay",
    "pil": "Pilipino",
    "plw": "Paluan",
    "plt": "Plateau Malagasy",
    "pms": "Piedmontese",
    "pmy": "Papuan Malay",
    "pnb": "Western Punjabi",
    "ppl": "Pipil",
    "prs": "Dari Persian",
    "pry": "Pray",
    "psi": "Pali",
    "pus": "Pushto/Pashto",
    "que": "Quechua",
    "roh": "Romansh",
    "roi": "Rotokas",
    "rom": "Romani",
    "ron": "Romanian",
    "rsa": "Rundi",
    "rus": "Russian",
    "rwa": "Kinyarwanda",
    "sad": "Sadri",
    "sag": "Sango",
    "sah": "Sakha",
    "sam": "Samaritan Aramaic",
    "san": "Sanskrit",
    "sat": "Santali",
    "scn": "Sicilian",
    "sco": "Scots",
    "sdh": "Southern Kurdish",
    "shn": "Shan",
    "sin": "Sinhala",
    "slk": "Slovak",
    "slv": "Slovenian",
    "sma": "Southern Sami",
    "smj": "Lule Sami",
    "smn": "Inari Sami",
    "sms": "Skolt Sami",
    "sna": "Shona",
    "snd": "Sindhi",
    "som": "Somali",
    "sot": "Sotho",
    "spa": "Spanish",
    "spl": "Selepet",
    "srd": "Sardinian",
    "srp": "Serbian",
    "ssw": "Swati",
    "sun": "Sundanese",
    "swe": "Swedish",
    "swh": "Swahili",
    "szl": "Silesian",
    "tam": "Tamil",
    "tar": "Tarahumara",
    "tat": "Tatar",
    "tel": "Telugu",
    "tem": "Temne",
    "teo": "Teso",
    "ter": "Terena",
    "tet": "Tetum",
    "tgk": "Tajik",
    "tgl": "Tagalog",
    "tha": "Thai",
    "tir": "Tigrinya",
    "tiv": "Tiv",
    "tkk": "Tkelma",
    "tlh": "Klingon",
    "tll": "Tetela",
    "tly": "Talysh",
    "tmh": "Tamashek",
    "tmr": "Tamarshek",
    "tms": "Turkmen",
    "tmy": "Taimyr Tatar",
    "tod": "Toma",
    "ton": "Tongan",
    "tpi": "Tok Pisin",
    "tpm": "Tlingit",
    "tqo": "Toaripi",
    "tru": "Turoyo",
    "tsd": "Tsakonian",
    "tsn": "Tswana",
    "tso": "Tsonga",
    "ttt": "Tat",
    "tui": "Tupian",
    "tum": "Tumbuka",
    "tup": "Tupi",
    "tur": "Turkish",
    "twi": "Twi",
    "twq": "Tasawaq",
    "twy": "Twain",
    "tyv": "Tuvinian",
    "tzm": "Tamazight",
    "uig": "Uighur",
    "ukr": "Ukrainian",
    "umb": "Umbundu",
    "unk": "Unknown",
    "upo": "Upra",
    "urb": "Urubú-Kaapor",
    "urd": "Urdu",
    "uzn": "Uzbek",
    "vec": "Venetian",
    "vel": "Venetian",
    "vie": "Vietnamese",
    "viet": "Vietnamese",
    "vls": "West Flemish",
    "vmh": "Vetom",
    "war": "Waray-Waray",
    "wbp": "Warlpiri",
    "wol": "Wolof",
    "wuu": "Wu Chinese",
    "xal": "Kalmyk",
    "xbo": "Xhosa",
    "xho": "Xhosa",
    "xmf": "Mingrelian",
    "xpf": "Xingó",
    "yao": "Yao",
    "yap": "Yapese",
    "ybb": "Yemba",
    "ydd": "Eastern Yiddish",
    "yea": "Yeanling",
    "yeu": "Yecuana",
    "ygr": "Yagaria",
    "yid": "Yiddish",
    "yin": "Yindjibarndi",
    "yli": "Yali",
    "yls": "Yankunytjatjara",
    "yly": "Nyang'le",
    "yno": "Yangoan",
    "yom": "Yombe",
    "yon": "Yonuo",
    "yor": "Yoruba",
    "ype": "Yapese",
    "yrl": "Nheengatu",
    "yua": "Yucateco",
    "yue": "Cantonese",
    "yum": "Yumanoid",
    "yup": "Yupik",
    "yus": "Yupno",
    "zai": "Zaitian",
    "zam": "Mam",
    "zap": "Zapotec",
    "zaq": "Ari",
    "zea": "Zealandic",
    "zeh": "Zenaga",
    "zen": "Zenaga",
    "zgh": "Standard Moroccan Tamazight",
    "zho": "Chinese (generic)",
    "zhx": "Chinese",
    "zia": "Zia",
    "zib": "Zilberman",
    "zil": "Zilberman",
    "zln": "Laze",
    "zlw": "West Slavic",
    "zmi": "Negeri Sembilan Malay",
    "zna": "Dzunarian",
    "zne": "Zanean",
    "zni": "Zuni",
    "zoo": "Zoomorphic",
    "zro": "Zoro",
    "zsm": "Standard Malay",
    "ztu": "Zotung",
    "zua": "Zuni",
    "zul": "Zulu",
    "zum": "Zuma",
    "zun": "Zuni",
    "zwa": "Swazi",
    "zxx": "No linguistic content",
    "zyg": "Zyrian",
    "zyx": "Zyrian",
    "zyy": "Zyrian",
}

# Build a mapping from locale (ll_CC) to NLLB language code
LOCALE_TO_NLLB_CODE = {}

# From the main table
for iso_639_3, (name, variants) in NLLB_SUPPORTED_LANGUAGES.items():
    for variant in variants:
        # Extract language code
        if "_" in variant:
            lang_code = variant.split("_")[0]
            LOCALE_TO_NLLB_CODE[variant] = iso_639_3
        else:
            LOCALE_TO_NLLB_CODE[variant] = iso_639_3

# Additional manual mappings based on common issues
LOCALE_OVERRIDES = {
    "pt_BR": "por",      # Portuguese (Brazil) -> Portuguese
    "pt_PT": "por",      # Portuguese (Portugal) -> Portuguese
    "en_US": "eng",      # English (US)
    "en_GB": "eng",      # English (GB)
    "en_AU": "eng",      # English (Australia)
    "en_CA": "eng",      # English (Canada)
    "en_NZ": "eng",      # English (New Zealand)
    "es_ES": "spa",      # Spanish (Spain)
    "es_MX": "spa",      # Spanish (Mexico)
    "es_AR": "spa",      # Spanish (Argentina)
    "fr_FR": "fra",      # French (France)
    "fr_CA": "fra",      # French (Canada)
    "fr_BE": "fra",      # French (Belgium)
    "de_DE": "deu",      # German (Germany)
    "de_AT": "deu",      # German (Austria)
    "de_CH": "deu",      # German (Switzerland)
    "zh_CN": "zho_Hans", # Chinese Simplified
    "zh_TW": "zho_Hant", # Chinese Traditional
    "zh_HK": "zho_Hant", # Hong Kong (Traditional)
    "zh_SG": "zho_Hans", # Singapore (Simplified)
    "ja_JP": "jpn",      # Japanese
    "ko_KR": "kor",      # Korean
    "ru_RU": "rus",      # Russian
    "ar_SA": "ara",      # Arabic (Saudi Arabia)
    "ar_AE": "ara",      # Arabic (UAE)
    "ar_EG": "ara",      # Arabic (Egypt)
    "hi_IN": "hin",      # Hindi (India)
    "th_TH": "tha",      # Thai
    "id_ID": "ind",      # Indonesian
    "vi_VN": "vie",      # Vietnamese
}

# Update the mapping
LOCALE_TO_NLLB_CODE.update(LOCALE_OVERRIDES)


def analyze_locale_compatibility(phase_a_json: Path) -> dict:
    """Analyze QuestLog locales against NLLB supported languages."""
    
    with open(phase_a_json, "r", encoding="utf-8") as f:
        inventory = json.load(f)
    
    all_locales = set(inventory["all_locales"])
    
    supported = []
    partially_supported = []
    unsupported = []
    unknown = []
    
    for locale in sorted(all_locales):
        if locale in LOCALE_TO_NLLB_CODE:
            nllb_code = LOCALE_TO_NLLB_CODE[locale]
            info = {
                "locale": locale,
                "nllb_code": nllb_code,
                "file_count": len(inventory["by_locale"].get(locale, {}).get("files", []))
            }
            
            # Try to extract language from code
            if "_" in locale:
                lang, country = locale.split("_")
            else:
                lang = locale
                country = None
            
            # Check if language base is supported
            if nllb_code and nllb_code in NLLB_SUPPORTED_LANGUAGES:
                lang_name = NLLB_SUPPORTED_LANGUAGES[nllb_code][0]
                info["language_name"] = lang_name
                info["supported"] = True
                supported.append(info)
            elif nllb_code and nllb_code in NLLB_ADDITIONAL_LANGS:
                lang_name = NLLB_ADDITIONAL_LANGS.get(nllb_code, "Unknown")
                info["language_name"] = lang_name
                info["supported"] = True
                supported.append(info)
            else:
                # Partially supported or edge case
                info["language_name"] = "Unknown"
                info["supported"] = False
                partially_supported.append(info)
        else:
            # Try to guess from locale structure
            if "_" in locale:
                lang, country = locale.split("_")
            else:
                lang = locale
                country = None
            
            info = {
                "locale": locale,
                "nllb_code": None,
                "language_code": lang,
                "country_code": country,
                "file_count": len(inventory["by_locale"].get(locale, {}).get("files", [])),
                "reason": "No mapping found in NLLB compatibility table"
            }
            unknown.append(info)
    
    return {
        "total_locales_in_corpus": len(all_locales),
        "supported_count": len(supported),
        "partially_supported_count": len(partially_supported),
        "unknown_count": len(unknown),
        "supported_locales": supported,
        "partially_supported_locales": partially_supported,
        "unknown_locales": unknown,
        "nllb_language_count": len(NLLB_SUPPORTED_LANGUAGES),
    }


def main():
    inventory_file = Path(r"C:\projetos1\visualcode\poliglota\reports\phase_a_inventory.json")
    if not inventory_file.exists():
        print(f"Error: {inventory_file} not found")
        return 1
    
    print("=" * 80)
    print("PHASE B — LANGUAGE/MODEL COMPATIBILITY AUDIT")
    print("=" * 80)
    
    result = analyze_locale_compatibility(inventory_file)
    
    print(f"\nCOMPATIBILITY SUMMARY")
    print("-" * 80)
    print(f"Total locales in corpus:      {result['total_locales_in_corpus']}")
    print(f"Supported by NLLB:            {result['supported_count']}")
    print(f"Partially/Edge cases:         {result['partially_supported_count']}")
    print(f"Unknown/Unmapped:             {result['unknown_count']}")
    print(f"NLLB language codes available: {result['nllb_language_count']}")
    
    # Save results
    report_file = Path(r"C:\projetos1\visualcode\poliglota\reports\phase_b_compatibility.json")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[OK] Full compatibility report saved to: {report_file}")
    
    # Show some supported examples
    print(f"\nSUPPORTED LOCALES (sample of {min(20, len(result['supported_locales']))})")
    print("-" * 80)
    for info in result["supported_locales"][:20]:
        print(f"{info['locale']:10s} -> {info.get('nllb_code', '?'):10s} ({info['language_name']})")
    
    # Show unknown
    if result["unknown_locales"]:
        print(f"\nUNKNOWN/UNMAPPED LOCALES (count: {len(result['unknown_locales'])})")
        print("-" * 80)
        for info in result["unknown_locales"][:10]:
            print(f"{info['locale']:10s} (language={info.get('language_code')}, country={info.get('country_code')})")
    
    return 0


if __name__ == "__main__":
    exit(main())
