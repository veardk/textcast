"""Shared helpers: time formatting, language utilities, work-dir file access.

Work dir layout: textcast/output/.work/<slug>/ holds what ingest wrote (ir.json, source/); each target
language gets its own folder beside it, textcast/output/.work/<slug>/<lang>/ (enrich.json, translations/,
ir.lock). Every command except ingest takes that language folder.
"""
import hashlib
import json
import re
import unicodedata
from pathlib import Path

IR_FILE = "ir.json"
ENRICH_FILE = "enrich.json"
TRANSLATIONS_DIR = "translations"
LOCK_FILE = "ir.lock"

LANG_NAMES = {
    "zh": "中文", "zh-cn": "简体中文", "zh-hans": "简体中文", "zh-tw": "繁體中文",
    "zh-hant": "繁體中文", "zh-hk": "繁體中文", "en": "English", "ja": "日本語",
    "ko": "한국어", "fr": "Français", "de": "Deutsch", "es": "Español",
    "ru": "Русский", "pt": "Português", "pt-br": "Português (Brasil)", "pt-pt": "Português (Portugal)",
    "it": "Italiano", "ar": "العربية", "hi": "हिन्दी", "vi": "Tiếng Việt", "th": "ไทย",
    "id": "Bahasa Indonesia", "ms": "Bahasa Melayu", "tr": "Türkçe", "nl": "Nederlands",
    "pl": "Polski", "uk": "Українська", "sv": "Svenska", "he": "עברית", "fa": "فارسی",
    "ur": "اردو", "bn": "বাংলা", "fil": "Filipino",
}

RTL_LANGS = {"ar", "he", "fa", "ur"}


def is_rtl(code: str | None) -> bool:
    return lang_base(code) in RTL_LANGS


def lang_base(code: str | None) -> str:
    return (code or "").lower().replace("_", "-").split("-")[0]


def same_lang(a: str | None, b: str | None) -> bool:
    """zh-CN and zh-TW count as different targets; en-US and en do not."""
    if not a or not b:
        return False
    a, b = a.lower(), b.lower()
    if lang_base(a) != lang_base(b):
        return False
    if lang_base(a) == "zh":
        trad = ("tw", "hant", "hk")
        return any(t in a for t in trad) == any(t in b for t in trad)
    return True


def norm_lang(code: str | None) -> str | None:
    """One spelling per language: zh / zh-cn / zh-Hans → zh-CN, zh-hant → zh-TW, pt_br → pt-BR."""
    if not code:
        return code
    parts = code.strip().replace("_", "-").split("-")
    base, low = parts[0].lower(), code.lower()
    if base == "zh":
        return "zh-HK" if "hk" in low else "zh-TW" if ("tw" in low or "hant" in low) else "zh-CN"
    rest = [p.upper() if len(p) == 2 else p.title() if len(p) == 4 else p.lower() for p in parts[1:]]
    return "-".join([base] + rest)


def ir_fingerprint(ir: dict) -> str:
    """Identifies the segment list translations are keyed to (ids + text)."""
    data = json.dumps([[s["id"], s["text"]] for s in ir["segments"]], ensure_ascii=False)
    return hashlib.sha1(data.encode("utf-8")).hexdigest()[:16]


def lang_name(code: str | None) -> str:
    if not code:
        return "原文"
    c = code.lower()
    return LANG_NAMES.get(c) or LANG_NAMES.get(lang_base(c)) or code


def is_cjk_lang(code: str | None) -> bool:
    return lang_base(code) in ("zh", "ja", "ko")


def guess_lang(text: str) -> str | None:
    """Script-based guess. You confirm or overrides it in enrich.json."""
    counts = {"han": 0, "kana": 0, "hangul": 0, "cyrillic": 0, "latin": 0, "arabic": 0}
    for ch in text[:20000]:
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        if "CJK" in name:
            counts["han"] += 1
        elif "HIRAGANA" in name or "KATAKANA" in name:
            counts["kana"] += 1
        elif "HANGUL" in name:
            counts["hangul"] += 1
        elif "CYRILLIC" in name:
            counts["cyrillic"] += 1
        elif "ARABIC" in name:
            counts["arabic"] += 1
        elif "LATIN" in name:
            counts["latin"] += 1
    if not any(counts.values()):
        return None
    if counts["kana"] > counts["han"] * 0.1 and counts["kana"] > 20:
        return "ja"
    top = max(counts, key=counts.get)
    return {"han": "zh", "hangul": "ko", "cyrillic": "ru", "arabic": "ar", "latin": "en", "kana": "ja"}[top]


def fmt_ts(ms: int, long: bool = False) -> str:
    s = max(0, int(ms)) // 1000
    h, m, sec = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if long or h else f"{m:02d}:{sec:02d}"


def fmt_dur(ms: int) -> str:
    s = int(ms) // 1000
    if s >= 3600:
        return f"{s // 3600}h {s % 3600 // 60:02d}m"
    return f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


_SENT_END = re.compile(r"[.?!。！？…]+[\"'”’」』）)\]】]*$")


def ends_sentence(text: str) -> bool:
    return bool(_SENT_END.search(text.strip()))


def text_units(text: str) -> int:
    """Rough reading length: CJK characters count as ~3 Latin characters."""
    return sum(3 if ord(c) > 0x2E80 else 1 for c in text)


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def load_translations(work: Path, enrich: dict) -> dict:
    """Merge enrich.translations with every translations/*.json batch (later files win)."""
    merged = {str(k): v for k, v in (enrich.get("translations") or {}).items()}
    tdir = work / TRANSLATIONS_DIR
    if tdir.is_dir():
        for f in sorted(tdir.glob("*.json")):
            try:
                batch = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise ValueError(f"{f} is not valid JSON ({e}); rewrite that batch file") from None
            merged.update({str(k): v for k, v in batch.items()})
    return merged
